import { jsonResponse } from "../_lib.js";

// Lets the pricing page warn before checkout if the email the customer is
// about to pay with already has an active license - Payment Links have no
// account system and create a brand-new Stripe customer on every checkout,
// so nothing upstream of this stops someone (or a double-click) from paying
// twice for the same product under the same email otherwise.
export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const email = (url.searchParams.get("email") || "").trim().toLowerCase();
  if (!email) return jsonResponse({ has_active_license: false });

  const row = await env.DB.prepare(
    `SELECT tier, created_at FROM licenses WHERE email = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1`,
  )
    .bind(email)
    .first();

  if (!row) return jsonResponse({ has_active_license: false });
  return jsonResponse({ has_active_license: true, tier: row.tier, since: row.created_at });
}
