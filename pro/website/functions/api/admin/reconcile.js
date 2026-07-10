import { getAffiliateSession, jsonResponse, normalizeEmail, runReconciliation } from "../../_affiliate.js";
import { runLockedIntegrityGate } from "../../_affiliate_integrity_lock.js";

export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);
    const actor = `admin:${normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)}`;
    const reconciliation = await runReconciliation(env, actor);
    const integrity = await runLockedIntegrityGate(env, actor);
    const blocked = reconciliation.status !== "ok" || integrity.status !== "ok";
    return jsonResponse({ reconciliation, integrity }, blocked ? 409 : 200);
  } catch (error) {
    console.error("affiliate reconciliation failed", error);
    const status = error.code === "integrity_check_busy" ? 409 : 500;
    return jsonResponse({ error: error.code || "reconciliation_failed", message: String(error?.message || error) }, status);
  }
}
