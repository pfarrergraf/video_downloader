import { jsonResponse, sha256Hex } from "../../_lib.js";
import { affiliateFlags, audit, isAffiliateAdmin, normalizeAffiliateCode, normalizeCampaignSlug } from "../../_affiliate.js";
import { markCommissionPaid, releaseMatureCommissions } from "../../_affiliate_commissions.js";
import { cleanupAffiliateRetention } from "../../_affiliate_retention.js";

function unauthorized() {
  return jsonResponse({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
}

export async function onRequestGet({ request, env }) {
  const flags = affiliateFlags(env);
  if (!flags.admin || !env.DB) return jsonResponse({ error: "affiliate_admin_not_enabled" }, 404);
  if (!(await isAffiliateAdmin(request, env))) return unauthorized();
  const affiliates = await env.DB.prepare(
    `SELECT a.id, a.code, a.display_name, a.status, a.commission_type,
            a.commission_value_minor, a.commission_rate_bps, a.created_at,
            a.approved_at, a.disabled_at,
            (SELECT COUNT(*) FROM referral_clicks c WHERE c.affiliate_id = a.id) AS clicks,
            (SELECT COUNT(*) FROM install_attributions i WHERE i.affiliate_id = a.id) AS installs,
            (SELECT COUNT(*) FROM affiliate_purchases p WHERE p.affiliate_id = a.id AND p.status = 'verified') AS purchases,
            (SELECT COALESCE(SUM(c.commission_amount_minor), 0) FROM affiliate_commissions c
             WHERE c.affiliate_id = a.id AND c.status IN ('pending', 'payable', 'paid')) AS commission_minor
     FROM affiliates a ORDER BY a.created_at DESC LIMIT 500`,
  ).all();
  return jsonResponse({ affiliates: affiliates.results || [] });
}

export async function onRequestPost({ request, env }) {
  const flags = affiliateFlags(env);
  if (!flags.admin || !env.DB) return jsonResponse({ error: "affiliate_admin_not_enabled" }, 404);
  if (!(await isAffiliateAdmin(request, env))) return unauthorized();
  let body;
  try { body = await request.json(); } catch { return jsonResponse({ error: "invalid JSON" }, 400); }
  const now = Math.floor(Date.now() / 1000);
  if (body?.action === "release") return jsonResponse(await releaseMatureCommissions(env, body.limit));
  if (body?.action === "retention") {
    return jsonResponse(await cleanupAffiliateRetention(env, { dryRun: body.dry_run !== false }));
  }
  if (body?.action === "create_access_token") {
    const affiliateId = typeof body.affiliate_id === "string" ? body.affiliate_id.trim() : "";
    const affiliate = await env.DB.prepare(`SELECT id, status FROM affiliates WHERE id = ?`).bind(affiliateId).first();
    if (!affiliate || affiliate.status !== "active") return jsonResponse({ error: "active affiliate not found" }, 404);
    const token = `afp_${crypto.randomUUID()}_${crypto.randomUUID()}`;
    const id = crypto.randomUUID();
    const now = Math.floor(Date.now() / 1000);
    await env.DB.prepare(
      `INSERT INTO affiliate_access_tokens (id, affiliate_id, token_hash, label, status, created_at)
       VALUES (?, ?, ?, ?, 'active', ?)`,
    ).bind(id, affiliateId, await sha256Hex(token), typeof body.label === "string" ? body.label.trim().slice(0, 120) : null, now).run();
    await audit(env, "affiliate.access_token.created", "affiliate", affiliateId, "token returned once", "admin");
    return jsonResponse({ id, affiliate_id: affiliateId, token }, 201);
  }
  if (body?.action === "revoke_access_token") {
    const id = typeof body.id === "string" ? body.id.trim() : "";
    const now = Math.floor(Date.now() / 1000);
    const result = await env.DB.prepare(
      `UPDATE affiliate_access_tokens SET status = 'revoked', revoked_at = ? WHERE id = ? AND status = 'active'`,
    ).bind(now, id).run();
    if (!result.meta?.changes) return jsonResponse({ error: "active token not found" }, 404);
    await audit(env, "affiliate.access_token.revoked", "affiliate_access_token", id, "manual revoke", "admin");
    return jsonResponse({ id, revoked: true });
  }
  if (body?.action === "mark_paid") {
    const paid = await markCommissionPaid(env, { id: body.id, paymentReference: body.payment_reference });
    return paid ? jsonResponse({ paid: true }) : jsonResponse({ error: "commission not payable or not found" }, 409);
  }
  if (body?.action === "hold" || body?.action === "clear_hold") {
    const id = typeof body.id === "string" ? body.id.trim() : "";
    if (!id) return jsonResponse({ error: "commission id is required" }, 400);
    const now = Math.floor(Date.now() / 1000);
    const target = body.action === "hold" ? "fraud_hold" : "pending";
    const result = await env.DB.prepare(
      `UPDATE affiliate_commissions SET status = ?, void_reason = CASE WHEN ? = 'fraud_hold' THEN ? ELSE void_reason END,
         updated_at = ? WHERE id = ? AND status IN ('pending', 'payable', 'fraud_hold')`,
    ).bind(target, target, typeof body.reason === "string" ? body.reason.trim().slice(0, 240) : "manual review", now, id).run();
    if (!result.meta?.changes) return jsonResponse({ error: "commission not found or already paid/voided" }, 409);
    await audit(env, `affiliate.commission.${body.action}`, "commission", id, body.reason || "manual review", "admin");
    if (body.action === "hold") await audit(env, "affiliate.fraud.flagged", "commission", id, body.reason || "manual review", "admin");
    return jsonResponse({ id, status: target });
  }
  if (body?.action === "set_status") {
    const id = typeof body.id === "string" ? body.id.trim() : "";
    const status = ["pending", "active", "disabled", "rejected"].includes(body.status) ? body.status : null;
    if (!id || !status) return jsonResponse({ error: "id and valid status are required" }, 400);
    const result = await env.DB.prepare(
      `UPDATE affiliates SET status = ?, approved_at = CASE WHEN ? = 'active' THEN COALESCE(approved_at, ?) ELSE approved_at END,
         disabled_at = CASE WHEN ? IN ('disabled', 'rejected') THEN ? ELSE NULL END, updated_at = ? WHERE id = ?`,
    ).bind(status, status, now, status, now, now, id).run();
    if (!result.meta?.changes) return jsonResponse({ error: "affiliate not found" }, 404);
    await audit(env, "affiliate.status.changed", "affiliate", id, status, "admin");
    return jsonResponse({ id, status });
  }
  if (body?.action === "campaign") {
    const affiliateId = typeof body.affiliate_id === "string" ? body.affiliate_id.trim() : "";
    const slug = normalizeCampaignSlug(body.slug);
    if (!affiliateId || !slug) return jsonResponse({ error: "affiliate_id and valid slug are required" }, 400);
    const affiliate = await env.DB.prepare(`SELECT id FROM affiliates WHERE id = ?`).bind(affiliateId).first();
    if (!affiliate) return jsonResponse({ error: "affiliate not found" }, 404);
    const id = crypto.randomUUID();
    try {
      await env.DB.prepare(
        `INSERT INTO affiliate_campaigns (id, affiliate_id, slug, source, status, created_at, updated_at)
         VALUES (?, ?, ?, ?, 'active', ?, ?)`,
      ).bind(id, affiliateId, slug, typeof body.source === "string" ? body.source.trim().slice(0, 80) : null, now, now).run();
    } catch { return jsonResponse({ error: "campaign already exists or is invalid" }, 409); }
    return jsonResponse({ id, affiliate_id: affiliateId, slug }, 201);
  }
  const code = normalizeAffiliateCode(body?.code);
  const displayName = typeof body?.display_name === "string" ? body.display_name.trim() : "";
  if (!code || !displayName || displayName.length > 120) return jsonResponse({ error: "valid code and display_name are required" }, 400);
  const status = body.status === "active" ? "active" : "pending";
  const commissionType = body.commission_type === "percentage" ? "percentage" : "fixed";
  const valueMinor = Number.isInteger(body.commission_value_minor) ? body.commission_value_minor : 0;
  const rateBps = Number.isInteger(body.commission_rate_bps) ? body.commission_rate_bps : 0;
  if (valueMinor < 0 || rateBps < 0 || rateBps > 10000) return jsonResponse({ error: "invalid commission policy" }, 400);
  const id = crypto.randomUUID();
  try {
    await env.DB.prepare(
      `INSERT INTO affiliates
        (id, code, display_name, status, commission_type, commission_value_minor,
         commission_rate_bps, created_at, approved_at, disabled_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)`,
    ).bind(id, code, displayName, status, commissionType, valueMinor, rateBps, now, status === "active" ? now : null, now).run();
  } catch { return jsonResponse({ error: "affiliate code already exists" }, 409); }
  return jsonResponse({ id, code, status }, 201);
}
