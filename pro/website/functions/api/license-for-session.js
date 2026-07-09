import { jsonResponse } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id");
  if (!sessionId) return jsonResponse({ found: false, error: "missing session_id" }, 400);

  const row = await env.DB.prepare(
    `SELECT license_key, tier, email FROM licenses WHERE stripe_checkout_session_id = ?`,
  )
    .bind(sessionId)
    .first();

  if (!row) return jsonResponse({ found: false });

  // Payment Links create a brand-new Stripe customer on every checkout, even
  // with an identical email - nothing upstream stops someone from buying
  // twice by accident (double-clicking, retrying after a slow/confusing
  // checkout). Surfacing it here, right after a successful purchase, is the
  // only place we can catch it before it turns into a support/refund ticket
  // days later.
  const otherActive = await env.DB.prepare(
    `SELECT COUNT(*) as count FROM licenses
     WHERE email = ? AND status = 'active' AND stripe_checkout_session_id != ?`,
  )
    .bind(row.email, sessionId)
    .first();

  return jsonResponse({
    found: true,
    license_key: row.license_key,
    tier: row.tier,
    other_active_licenses: otherActive?.count ?? 0,
  });
}
