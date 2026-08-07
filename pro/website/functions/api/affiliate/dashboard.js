import { jsonResponse, sha256Hex } from "../../_lib.js";
import { affiliateFlags, nowSeconds } from "../../_affiliate.js";

function unauthorized() {
  return jsonResponse({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
}

function seconds(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export async function onRequestGet({ request, env }) {
  const flags = affiliateFlags(env);
  if (!flags.enabled || !flags.dashboard || !env.DB) return jsonResponse({ error: "affiliate_dashboard_not_enabled" }, 404);
  const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!supplied || supplied.length > 200) return unauthorized();
  const tokenHash = await sha256Hex(supplied);
  const token = await env.DB.prepare(
    `SELECT t.id, t.affiliate_id, a.code, a.display_name, a.status
     FROM affiliate_access_tokens t JOIN affiliates a ON a.id = t.affiliate_id
     WHERE t.token_hash = ? AND t.status = 'active' AND a.status = 'active'`,
  ).bind(tokenHash).first();
  if (!token) return unauthorized();
  const now = nowSeconds(env);
  await env.DB.prepare(`UPDATE affiliate_access_tokens SET last_used_at = ? WHERE id = ?`).bind(now, token.id).run();
  const url = new URL(request.url);
  const to = Math.min(seconds(url.searchParams.get("to"), now), now);
  const from = Math.min(to, Math.max(seconds(url.searchParams.get("from"), to - 30 * 24 * 60 * 60), to - 366 * 24 * 60 * 60));
  const [campaigns, commissions, totals] = await Promise.all([
    env.DB.prepare(
      `SELECT c.slug, c.source,
        (SELECT COUNT(*) FROM referral_clicks r WHERE r.campaign_id = c.id AND r.created_at BETWEEN ? AND ?) AS clicks,
        (SELECT COUNT(*) FROM install_attributions i WHERE i.campaign_id = c.id AND i.attributed_at BETWEEN ? AND ?) AS installs,
        (SELECT COUNT(*) FROM affiliate_purchases p WHERE p.affiliate_id = c.affiliate_id AND p.install_attribution_id IN
          (SELECT i.id FROM install_attributions i WHERE i.campaign_id = c.id) AND p.status = 'verified' AND p.created_at BETWEEN ? AND ?) AS purchases
       FROM affiliate_campaigns c WHERE c.affiliate_id = ? ORDER BY c.slug LIMIT 500`,
    ).bind(from, to, from, to, from, to, token.affiliate_id).all(),
    env.DB.prepare(
      `SELECT status, COUNT(*) AS count, COALESCE(SUM(commission_amount_minor), 0) AS amount_minor
       FROM affiliate_commissions WHERE affiliate_id = ? AND created_at BETWEEN ? AND ? GROUP BY status ORDER BY status`,
    ).bind(token.affiliate_id, from, to).all(),
    env.DB.prepare(
      `SELECT
        (SELECT COUNT(*) FROM referral_clicks WHERE affiliate_id = ? AND created_at BETWEEN ? AND ?) AS clicks,
        (SELECT COUNT(*) FROM install_attributions WHERE affiliate_id = ? AND attributed_at BETWEEN ? AND ?) AS installs,
        (SELECT COUNT(*) FROM affiliate_purchases WHERE affiliate_id = ? AND status = 'verified' AND created_at BETWEEN ? AND ?) AS purchases`,
    ).bind(token.affiliate_id, from, to, token.affiliate_id, from, to, token.affiliate_id, from, to).first(),
  ]);
  const base = env.PUBLIC_BASE_URL || "https://downloadthat.app";
  return jsonResponse({
    affiliate: { code: token.code, display_name: token.display_name },
    links: [{ code: token.code, url: `${base.replace(/\/$/, "")}/r/${encodeURIComponent(token.code)}` }, ...(campaigns.results || []).map((campaign) => ({ code: token.code, campaign: campaign.slug, url: `${base.replace(/\/$/, "")}/r/${encodeURIComponent(token.code)}/${encodeURIComponent(campaign.slug)}` }))],
    window: { from, to },
    totals: totals || { clicks: 0, installs: 0, purchases: 0 },
    campaigns: campaigns.results || [],
    commissions: commissions.results || [],
    privacy: { raw_tokens: false, buyer_data: false, order_ids: false, device_data: false },
  });
}
