import { sha256Hex } from "./_lib.js";
import { affiliateFlags, audit, hashInstallId, nowSeconds } from "./_affiliate.js";

const HOLD_SECONDS = 30 * 24 * 60 * 60;

function moneyValue(affiliate, purchase) {
  if (affiliate.commission_type === "fixed") return Math.max(0, Number(affiliate.commission_value_minor) || 0);
  const gross = Number(purchase.amount_minor);
  const rate = Number(affiliate.commission_rate_bps) || 0;
  if (!Number.isInteger(gross) || gross < 0 || !Number.isInteger(rate)) return 0;
  return Math.floor(gross * rate / 10000);
}

async function linkPurchase(env, purchase, attribution, now) {
  const affiliate = await env.DB.prepare(
    `SELECT id, commission_type, commission_value_minor, commission_rate_bps
     FROM affiliates WHERE id = ? AND status = 'active'`,
  ).bind(attribution.affiliate_id).first();
  if (!affiliate) return { linked: false, reason: "affiliate_not_active" };
  const existing = await env.DB.prepare(
    `SELECT id FROM affiliate_purchases WHERE purchase_token_hash = ?`,
  ).bind(purchase.token_hash).first();
  if (existing) return { linked: true, idempotent: true, purchaseId: existing.id };

  const purchaseId = crypto.randomUUID();
  try {
    await env.DB.prepare(
      `INSERT INTO affiliate_purchases
        (id, affiliate_id, install_attribution_id, purchase_token_hash, order_id,
         product_id, amount_minor, currency, purchase_timestamp, status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?)`,
    ).bind(
      purchaseId,
      affiliate.id,
      attribution.id,
      purchase.token_hash,
      purchase.order_id,
      purchase.product_id,
      purchase.amount_minor,
      purchase.currency,
      purchase.purchase_completed_at,
      now,
      now,
    ).run();
  } catch (error) {
    const raced = await env.DB.prepare(
      `SELECT id FROM affiliate_purchases WHERE purchase_token_hash = ? OR (order_id IS NOT NULL AND order_id = ?)`,
    ).bind(purchase.token_hash, purchase.order_id).first();
    if (raced) return { linked: true, idempotent: true, purchaseId: raced.id };
    throw error;
  }
  const commissionAmount = moneyValue(affiliate, purchase);
  if (commissionAmount > 0) {
    await env.DB.prepare(
      `INSERT INTO affiliate_commissions
        (id, affiliate_id, affiliate_purchase_id, gross_amount_minor, commission_amount_minor,
         currency, status, available_at, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)`,
    ).bind(
      crypto.randomUUID(), affiliate.id, purchaseId, purchase.amount_minor, commissionAmount,
      purchase.currency, now + HOLD_SECONDS, now, now,
    ).run();
    await audit(env, "affiliate.commission.created", "affiliate_purchase", purchaseId);
  }
  await audit(env, "affiliate.purchase.attributed", "affiliate_purchase", purchaseId);
  return { linked: true, idempotent: false, purchaseId, commissionAmount };
}

export async function attributeVerifiedPurchase(env, { deviceId, purchaseToken = null }) {
  const flags = affiliateFlags(env);
  if (!flags.enabled || !flags.commission || !env.DB) return { linked: false, reason: "disabled" };
  if (typeof deviceId !== "string" || deviceId.length < 16 || deviceId.length > 256) return { linked: false, reason: "invalid_device" };
  const rawDeviceHash = await sha256Hex(deviceId);
  const installHash = await hashInstallId(env, deviceId);
  if (!installHash) return { linked: false, reason: "missing_hash_secret" };
  const attribution = await env.DB.prepare(
    `SELECT id, affiliate_id, attributed_at
     FROM install_attributions WHERE install_id_hash = ?`,
  ).bind(installHash).first();
  if (!attribution) return { linked: false, reason: "no_attribution" };
  const now = nowSeconds(env);
  if (now - Number(attribution.attributed_at) > 60 * 24 * 60 * 60) return { linked: false, reason: "outside_purchase_window" };
  const tokenHash = purchaseToken ? await sha256Hex(purchaseToken) : null;
  const query = tokenHash
    ? `SELECT token_hash, order_id, product_id, purchase_completed_at, NULL AS amount_minor, NULL AS currency
       FROM play_purchases WHERE token_hash = ? AND purchase_state = 'purchased'`
    : `SELECT token_hash, order_id, product_id, purchase_completed_at, NULL AS amount_minor, NULL AS currency
       FROM play_purchases WHERE purchase_device_id_hash = ? AND purchase_state = 'purchased'
       ORDER BY purchase_completed_at DESC LIMIT 10`;
  const rows = tokenHash
    ? { results: [await env.DB.prepare(query).bind(tokenHash).first()].filter(Boolean) }
    : await env.DB.prepare(query).bind(rawDeviceHash).all();
  const linked = [];
  for (const purchase of rows.results || []) linked.push(await linkPurchase(env, purchase, attribution, now));
  return { linked: linked.some((item) => item.linked), results: linked };
}

export async function voidAffiliatePurchase(env, { purchaseTokenHash, reason = "play_voided" }) {
  if (!env.DB || typeof purchaseTokenHash !== "string") return false;
  const row = await env.DB.prepare(
    `SELECT id FROM affiliate_purchases WHERE purchase_token_hash = ?`,
  ).bind(purchaseTokenHash).first();
  if (!row) return false;
  const now = nowSeconds(env);
  await env.DB.batch([
    env.DB.prepare(`UPDATE affiliate_purchases SET status = 'voided', updated_at = ? WHERE id = ?`).bind(now, row.id),
    env.DB.prepare(
      `UPDATE affiliate_commissions SET status = CASE WHEN status = 'paid' THEN 'clawback_due' ELSE 'voided' END,
       voided_at = ?, void_reason = ?, updated_at = ? WHERE affiliate_purchase_id = ? AND status NOT IN ('voided', 'clawback_due')`,
    ).bind(now, reason, now, row.id),
  ]);
  await audit(env, "affiliate.commission.voided", "affiliate_purchase", row.id, reason);
  await audit(env, "affiliate.purchase.voided", "affiliate_purchase", row.id, reason);
  if (/refund/i.test(reason)) await audit(env, "affiliate.purchase.refunded", "affiliate_purchase", row.id, reason);
  return true;
}

export async function releaseMatureCommissions(env, limit = 100) {
  if (!env.DB || !affiliateFlags(env).commission) return { released: 0, skipped: true };
  const now = nowSeconds(env);
  const rows = await env.DB.prepare(
    `SELECT id FROM affiliate_commissions WHERE status = 'pending' AND available_at <= ? ORDER BY available_at ASC LIMIT ?`,
  ).bind(now, Math.min(Math.max(Number(limit) || 100, 1), 1000)).all();
  let released = 0;
  for (const row of rows.results || []) {
    const result = await env.DB.prepare(
      `UPDATE affiliate_commissions SET status = 'payable', approved_at = ?, updated_at = ?
       WHERE id = ? AND status = 'pending' AND available_at <= ?`,
    ).bind(now, now, row.id, now).run();
    if (result.meta?.changes) { released += 1; await audit(env, "affiliate.commission.approved", "commission", row.id); }
  }
  return { released };
}

export async function markCommissionPaid(env, { id, paymentReference }) {
  if (!env.DB || typeof id !== "string" || typeof paymentReference !== "string" || !paymentReference.trim()) return false;
  const now = nowSeconds(env);
  const result = await env.DB.prepare(
    `UPDATE affiliate_commissions SET status = 'paid', paid_at = ?, payment_reference = ?, updated_at = ?
     WHERE id = ? AND status = 'payable'`,
  ).bind(now, paymentReference.trim().slice(0, 240), now, id).run();
  if (result.meta?.changes) await audit(env, "affiliate.commission.paid", "commission", id, "manual payout", "admin");
  return Boolean(result.meta?.changes);
}
