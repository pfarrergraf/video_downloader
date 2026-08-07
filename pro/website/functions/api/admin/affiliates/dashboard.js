import { jsonResponse } from "../../../_lib.js";
import { affiliateFlags, isAffiliateAdmin } from "../../../_affiliate.js";

function unauthorized() {
  return jsonResponse({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
}

function seconds(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export async function onRequestGet({ request, env }) {
  const flags = affiliateFlags(env);
  if (!flags.enabled || !flags.dashboard || !flags.admin || !env.DB) return jsonResponse({ error: "affiliate_dashboard_not_enabled" }, 404);
  if (!(await isAffiliateAdmin(request, env))) return unauthorized();
  const url = new URL(request.url);
  const now = Math.floor(Date.now() / 1000);
  const to = Math.min(seconds(url.searchParams.get("to"), now), now);
  const from = Math.min(to, Math.max(seconds(url.searchParams.get("from"), to - 30 * 24 * 60 * 60), to - 366 * 24 * 60 * 60));
  const [affiliateRows, commissionRows] = await Promise.all([
    env.DB.prepare(
      `SELECT a.code, a.display_name, a.status,
        (SELECT COUNT(*) FROM referral_clicks c WHERE c.affiliate_id = a.id AND c.created_at BETWEEN ? AND ?) AS clicks,
        (SELECT COUNT(*) FROM install_attributions i WHERE i.affiliate_id = a.id AND i.attributed_at BETWEEN ? AND ?) AS installs,
        (SELECT COUNT(*) FROM affiliate_purchases p WHERE p.affiliate_id = a.id AND p.status = 'verified' AND p.created_at BETWEEN ? AND ?) AS purchases
       FROM affiliates a ORDER BY a.code LIMIT 500`,
    ).bind(from, to, from, to, from, to).all(),
    env.DB.prepare(
      `SELECT status, COUNT(*) AS count, COALESCE(SUM(commission_amount_minor), 0) AS amount_minor
       FROM affiliate_commissions WHERE created_at BETWEEN ? AND ? GROUP BY status ORDER BY status`,
    ).bind(from, to).all(),
  ]);
  return jsonResponse({
    window: { from, to },
    affiliates: affiliateRows.results || [],
    commissions: commissionRows.results || [],
    privacy: { raw_tokens: false, buyer_data: false, row_level_purchase_feed: false },
  });
}
