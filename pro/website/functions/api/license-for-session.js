import { jsonResponse } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id");
  if (!sessionId) return jsonResponse({ found: false, error: "missing session_id" }, 400);

  const row = await env.DB.prepare(
    `SELECT license_key, tier FROM licenses WHERE stripe_checkout_session_id = ?`,
  )
    .bind(sessionId)
    .first();

  if (!row) return jsonResponse({ found: false });
  return jsonResponse({ found: true, license_key: row.license_key, tier: row.tier });
}
