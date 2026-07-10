import { jsonResponse } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id");
  if (!sessionId) return jsonResponse({ found: false, error: "missing session_id" }, 400);

  const row = await env.DB.prepare(
    `SELECT license_key, tier, deliver_at FROM licenses WHERE stripe_checkout_session_id = ?`,
  )
    .bind(sessionId)
    .first();

  if (!row) return jsonResponse({ found: false });

  // The buyer kept their 14-day withdrawal right, so the key stays sealed
  // until that period has passed - handing it over earlier would start the
  // "delivery" that voids the right. The success page shows the date; the
  // buyer returns to the same URL afterwards (it keeps working - the lookup
  // is against our own table, not against Stripe's session lifetime).
  const now = Math.floor(Date.now() / 1000);
  if (row.deliver_at != null && row.deliver_at > now) {
    return jsonResponse({ found: true, pending_delivery: true, deliver_at: row.deliver_at, tier: row.tier });
  }
  return jsonResponse({ found: true, license_key: row.license_key, tier: row.tier });
}
