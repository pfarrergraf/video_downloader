import { getAffiliateSession, jsonResponse, prepareAffiliatePayout } from "../../_affiliate.js";

export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);
    const body = await request.json().catch(() => ({}));
    const affiliateId = String(body.affiliate_id || "");
    if (!affiliateId) return jsonResponse({ error: "affiliate_id_required" }, 400);
    const result = await prepareAffiliatePayout(env, affiliateId, "system-payout-engine");
    return jsonResponse(result, result.status || 200);
  } catch (error) {
    console.error("payout preparation failed", error);
    return jsonResponse({ error: "payout_preparation_failed", message: String(error?.message || error) }, 500);
  }
}
