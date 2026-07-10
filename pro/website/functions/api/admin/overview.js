import { getAffiliateSession, jsonResponse, normalizeEmail } from "../../_affiliate.js";

export async function onRequestGet({ request, env }) {
  const session = await getAffiliateSession(request, env, "admin");
  if (!session) return jsonResponse({ error: "unauthorized" }, 401);

  const [controls, affiliates, payouts, reconciliations] = await Promise.all([
    env.DB.prepare(`SELECT * FROM affiliate_controls WHERE id = 'global'`).first(),
    env.DB.prepare(
      `SELECT id, slug, code, display_name, email, country, status,
              approved_sale_count, lifetime_approved_cents, lifetime_paid_cents,
              negative_balance_cents, created_at
         FROM affiliates ORDER BY created_at DESC LIMIT 500`,
    ).all(),
    env.DB.prepare(
      `SELECT p.*, a.display_name, a.code
         FROM affiliate_payouts p
         JOIN affiliates a ON a.id = p.affiliate_id
        ORDER BY p.prepared_at DESC LIMIT 200`,
    ).all(),
    env.DB.prepare(
      `SELECT * FROM affiliate_reconciliation_snapshots
        ORDER BY created_at DESC LIMIT 50`,
    ).all(),
  ]);

  return jsonResponse({
    admin: normalizeEmail(env.AFFILIATE_ADMIN_EMAIL),
    controls,
    affiliates: affiliates.results || [],
    payouts: payouts.results || [],
    reconciliations: reconciliations.results || [],
  });
}
