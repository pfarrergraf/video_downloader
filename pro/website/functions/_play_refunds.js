import { sha256Hex } from "./_lib.js";
import {
  decryptPurchaseToken,
  fetchPlayPurchase,
  normalizePurchase,
  refundPlayOrder,
  revokePlayPurchaseByToken,
  verifyAndApplyPlayPurchase,
} from "./_google_play.js";

const HOUR = 3600;
const DAY = 24 * HOUR;
const ALLOWED_REASONS = new Set(["technical_failure", "accidental_purchase", "other"]);

function publicRequest(row) {
  return {
    request_id: row.id,
    status: row.status,
    policy_reason: row.policy_reason,
    requested_at: row.requested_at,
    refunded_at: row.refunded_at ?? null,
    revoked: row.status === "refunded",
  };
}

function policyFor({ ageSeconds, reason, delivered, repeatedDeviceRefund, deviceMismatch, automationEnabled, hasOrderId }) {
  if (!hasOrderId) return { automatic: false, reason: "missing_refundable_order" };
  if (!automationEnabled) return { automatic: false, reason: "automation_disabled" };
  if (deviceMismatch) return { automatic: false, reason: "device_mismatch_manual_review" };
  if (repeatedDeviceRefund) return { automatic: false, reason: "repeat_refund_manual_review" };
  if (!Number.isFinite(ageSeconds) || ageSeconds < -300) {
    return { automatic: false, reason: "purchase_time_unavailable" };
  }
  if (ageSeconds <= 48 * HOUR) return { automatic: true, reason: "within_48_hours" };
  if (ageSeconds <= 14 * DAY && reason === "technical_failure" && !delivered) {
    return { automatic: true, reason: "technical_non_delivery_within_14_days" };
  }
  if (ageSeconds <= 14 * DAY) return { automatic: false, reason: "days_3_to_14_manual_review" };
  return { automatic: false, reason: "outside_14_day_window" };
}

async function executeRefund(env, row, purchaseToken, expectedStatus = "manual_review") {
  const claim = await env.DB.prepare(
    `UPDATE play_refund_requests SET status = 'processing', updated_at = ?, last_error = NULL
     WHERE id = ? AND status = ?`,
  ).bind(Math.floor(Date.now() / 1000), row.id, expectedStatus).run();
  if (!claim.meta?.changes) {
    const current = await env.DB.prepare(`SELECT * FROM play_refund_requests WHERE id = ?`).bind(row.id).first();
    return publicRequest(current || row);
  }

  try {
    const fresh = normalizePurchase(await fetchPlayPurchase(env, purchaseToken));
    const purchased = fresh.state === "PURCHASED" || fresh.state === "PURCHASE_STATE_PURCHASED";
    if (!purchased || !fresh.orderId || fresh.orderId !== row.order_id) {
      throw new Error("purchase no longer refundable or order changed");
    }
    await refundPlayOrder(env, row.order_id);
    await revokePlayPurchaseByToken(env, purchaseToken);
    const now = Math.floor(Date.now() / 1000);
    await env.DB.prepare(
      `UPDATE play_refund_requests SET status = 'refunded', decided_at = ?, refunded_at = ?,
       updated_at = ?, last_error = NULL WHERE id = ? AND status = 'processing'`,
    ).bind(now, now, now, row.id).run();
  } catch (error) {
    const now = Math.floor(Date.now() / 1000);
    await env.DB.prepare(
      `UPDATE play_refund_requests SET status = 'manual_review', updated_at = ?, last_error = ?
       WHERE id = ? AND status = 'processing'`,
    ).bind(now, String(error?.message || error).slice(0, 240), row.id).run();
    console.error("Google Play refund requires manual review", {
      requestId: row.id,
      message: String(error?.message || error),
    });
  }
  return publicRequest(await env.DB.prepare(`SELECT * FROM play_refund_requests WHERE id = ?`).bind(row.id).first());
}

export async function requestPlayRefund(env, { purchaseToken, deviceId, reason }) {
  if (!env.DB) throw Object.assign(new Error("DB is not configured"), { status: 500 });
  if (typeof deviceId !== "string" || deviceId.length < 16 || deviceId.length > 256) {
    throw Object.assign(new Error("invalid device id"), { status: 400 });
  }
  if (!ALLOWED_REASONS.has(reason)) throw Object.assign(new Error("invalid refund reason"), { status: 400 });

  if (typeof purchaseToken !== "string" || purchaseToken.length < 16 || purchaseToken.length > 4096) {
    throw Object.assign(new Error("invalid purchase token"), { status: 400 });
  }
  const tokenHash = await sha256Hex(purchaseToken);
  const existing = await env.DB.prepare(`SELECT * FROM play_refund_requests WHERE token_hash = ?`)
    .bind(tokenHash).first();
  if (existing) {
    if (existing.status === "refunded") await revokePlayPurchaseByToken(env, purchaseToken);
    return publicRequest(existing);
  }

  // This is the decisive anti-forgery check: the caller-supplied token is
  // checked live against Google before any request can reach the refund API.
  const verified = await verifyAndApplyPlayPurchase(env, purchaseToken, { deviceId });
  if (!verified.entitled || verified.state !== "purchased") {
    throw Object.assign(new Error("no refundable Google Play purchase"), { status: 403 });
  }
  const purchase = await env.DB.prepare(
    `SELECT order_id, purchase_completed_at, entitlement_delivered_at, purchase_device_id_hash
     FROM play_purchases WHERE token_hash = ? AND purchase_state = 'purchased'`,
  ).bind(tokenHash).first();
  if (!purchase) throw Object.assign(new Error("verified purchase mapping missing"), { status: 409 });
  const deviceHash = await sha256Hex(deviceId);
  const repeat = await env.DB.prepare(
    `SELECT id FROM play_refund_requests
     WHERE device_id_hash = ? AND status = 'refunded' AND token_hash <> ? LIMIT 1`,
  ).bind(deviceHash, tokenHash).first();
  const now = Math.floor(Date.now() / 1000);
  const policy = policyFor({
    ageSeconds: purchase.purchase_completed_at == null ? NaN : now - purchase.purchase_completed_at,
    reason,
    delivered: purchase.entitlement_delivered_at != null,
    repeatedDeviceRefund: Boolean(repeat),
    deviceMismatch: Boolean(purchase.purchase_device_id_hash && purchase.purchase_device_id_hash !== deviceHash),
    automationEnabled: env.PLAY_AUTOMATED_REFUNDS_ENABLED === "true",
    hasOrderId: Boolean(purchase.order_id),
  });
  const id = crypto.randomUUID();
  try {
    await env.DB.prepare(
      `INSERT INTO play_refund_requests
        (id, token_hash, order_id, device_id_hash, reason, status, policy_reason,
         requested_at, decided_at, refunded_at, updated_at, last_error)
       VALUES (?, ?, ?, ?, ?, 'manual_review', ?, ?, NULL, NULL, ?, NULL)`,
    ).bind(id, tokenHash, purchase.order_id, deviceHash, reason, policy.reason, now, now).run();
  } catch (error) {
    const raced = await env.DB.prepare(
      `SELECT * FROM play_refund_requests WHERE token_hash = ? OR (order_id IS NOT NULL AND order_id = ?) LIMIT 1`,
    ).bind(tokenHash, purchase.order_id).first();
    if (raced) return publicRequest(raced);
    throw error;
  }
  const row = await env.DB.prepare(`SELECT * FROM play_refund_requests WHERE id = ?`).bind(id).first();
  return policy.automatic ? executeRefund(env, row, purchaseToken) : publicRequest(row);
}

export async function markPlayEntitlementDelivered(env, { purchaseToken, deviceId }) {
  if (typeof purchaseToken !== "string" || purchaseToken.length < 16 || purchaseToken.length > 4096) {
    throw Object.assign(new Error("invalid purchase token"), { status: 400 });
  }
  if (typeof deviceId !== "string" || deviceId.length < 16 || deviceId.length > 256) {
    throw Object.assign(new Error("invalid device id"), { status: 400 });
  }
  const tokenHash = await sha256Hex(purchaseToken);
  const deviceHash = await sha256Hex(deviceId);
  const now = Math.floor(Date.now() / 1000);
  const result = await env.DB.prepare(
    `UPDATE play_purchases SET entitlement_delivered_at = COALESCE(entitlement_delivered_at, ?),
       purchase_device_id_hash = COALESCE(purchase_device_id_hash, ?), updated_at = ?
     WHERE token_hash = ? AND purchase_state = 'purchased'
       AND (purchase_device_id_hash IS NULL OR purchase_device_id_hash = ?)`,
  ).bind(now, deviceHash, now, tokenHash, deviceHash).run();
  if (!result.meta?.changes) throw Object.assign(new Error("verified purchase not found"), { status: 404 });
  return { delivered: true };
}

export async function listPlayRefunds(env) {
  const rows = await env.DB.prepare(
    `SELECT id, order_id, reason, status, policy_reason, requested_at, decided_at,
            refunded_at, updated_at, last_error
     FROM play_refund_requests ORDER BY requested_at DESC LIMIT 250`,
  ).all();
  return rows.results || [];
}

export async function decidePlayRefund(env, { id, approve }) {
  const row = await env.DB.prepare(
    `SELECT r.*, p.purchase_token_ciphertext, p.purchase_token_iv
     FROM play_refund_requests r JOIN play_purchases p ON p.token_hash = r.token_hash
     WHERE r.id = ?`,
  ).bind(id).first();
  if (!row) throw Object.assign(new Error("refund request not found"), { status: 404 });
  if (row.status !== "manual_review") return publicRequest(row);
  const now = Math.floor(Date.now() / 1000);
  if (!approve) {
    await env.DB.prepare(
      `UPDATE play_refund_requests SET status = 'rejected', decided_at = ?, updated_at = ?
       WHERE id = ? AND status = 'manual_review'`,
    ).bind(now, now, id).run();
    return publicRequest(await env.DB.prepare(`SELECT * FROM play_refund_requests WHERE id = ?`).bind(id).first());
  }
  const token = await decryptPurchaseToken(env, row.purchase_token_ciphertext, row.purchase_token_iv);
  return executeRefund(env, row, token);
}

export async function isRefundAdmin(request, env) {
  const expected = env.PLAY_REFUND_ADMIN_TOKEN;
  const authorization = request.headers.get("Authorization") || "";
  const supplied = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
  if (!expected || !supplied) return false;
  const [left, right] = await Promise.all([sha256Hex(supplied), sha256Hex(expected)]);
  return left === right;
}

export { policyFor, publicRequest };
