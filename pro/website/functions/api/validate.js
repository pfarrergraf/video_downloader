import { jsonResponse } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const key = url.searchParams.get("key");
  if (!key) return jsonResponse({ valid: false, error: "missing key" }, 400);

  const row = await env.DB.prepare(
    `SELECT tier, status, current_period_end FROM licenses WHERE license_key = ?`,
  )
    .bind(key)
    .first();

  if (!row) return jsonResponse({ valid: false });

  const now = Math.floor(Date.now() / 1000);
  const expired =
    row.status !== "active" ||
    (row.tier !== "lifetime" && row.current_period_end !== null && row.current_period_end < now);

  return jsonResponse({
    valid: !expired,
    tier: row.tier,
    status: expired ? "expired" : row.status,
  });
}
