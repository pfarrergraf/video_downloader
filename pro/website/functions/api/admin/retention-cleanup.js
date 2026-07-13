import { getAffiliateSession, jsonResponse } from "../../_affiliate.js";
import { purgeExpiredClicks, purgeStaleActivations } from "../../_gdpr.js";

// Admin-gated data-retention housekeeping. Pages Functions have no cron, so
// this is invoked on demand (or by an external scheduler hitting it with the
// admin session) to purge pseudonymous tracking rows that would otherwise grow
// without bound - expired affiliate_clicks and long-revoked device slots.
export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);

    const now = Math.floor(Date.now() / 1000);
    const clicksDeleted = await purgeExpiredClicks(env.DB, now);
    const activationsDeleted = await purgeStaleActivations(env.DB, now);

    return jsonResponse({
      ok: true,
      clicks_deleted: clicksDeleted,
      activations_deleted: activationsDeleted,
    });
  } catch (err) {
    return jsonResponse({ error: "retention_cleanup_failed", detail: String(err && err.message) }, 500);
  }
}
