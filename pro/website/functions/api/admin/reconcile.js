import { getAffiliateSession, jsonResponse, normalizeEmail, runReconciliation } from "../../_affiliate.js";

export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);
    const actor = `admin:${normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)}`;
    const result = await runReconciliation(env, actor);
    return jsonResponse(result, result.status === "blocked" ? 409 : 200);
  } catch (error) {
    console.error("affiliate reconciliation failed", error);
    return jsonResponse({ error: "reconciliation_failed", message: String(error?.message || error) }, 500);
  }
}
