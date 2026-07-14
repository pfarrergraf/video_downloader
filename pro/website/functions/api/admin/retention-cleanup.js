import { getAffiliateSession, jsonResponse, sha256Hex } from "../../_affiliate.js";
import { purgeExpiredClicks, purgeStaleActivations } from "../../_gdpr.js";

async function matchesCleanupToken(request, env) {
  const configured = String(env.RETENTION_CLEANUP_TOKEN || "");
  const match = (request.headers.get("Authorization") || "").match(/^Bearer\s+(.+)$/i);
  if (!configured || !match) return false;

  const [providedHash, configuredHash] = await Promise.all([
    sha256Hex(match[1]),
    sha256Hex(configured),
  ]);
  let difference = 0;
  for (let index = 0; index < configuredHash.length; index += 1) {
    difference |= providedHash.charCodeAt(index) ^ configuredHash.charCodeAt(index);
  }
  return difference === 0;
}

async function isAuthorized(request, env) {
  if (await matchesCleanupToken(request, env)) return true;
  return Boolean(await getAffiliateSession(request, env, "admin"));
}

// Admin-gated data-retention housekeeping. Pages Functions have no cron, so
// this is invoked on demand or by the GitHub Actions scheduler. Interactive
// calls use the admin session; automation uses a dedicated rotatable bearer
// token so it does not depend on a 30-day browser session.
export async function onRequestPost({ request, env }) {
  try {
    if (!(await isAuthorized(request, env))) {
      return jsonResponse({ error: "unauthorized" }, 401);
    }

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
