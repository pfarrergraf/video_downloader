import {
  getAffiliateSession,
  jsonResponse,
  markAffiliatePayoutPaid,
  normalizeEmail,
} from "../../_affiliate.js";

export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);
    const body = await request.json().catch(() => ({}));
    const payoutId = String(body.payout_id || "");
    const externalReference = String(body.external_reference || "").trim();
    if (!payoutId) return jsonResponse({ error: "payout_id_required" }, 400);
    const actor = `admin:${normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)}`;
    const result = await markAffiliatePayoutPaid(env, payoutId, actor, externalReference);
    return jsonResponse(result, result.status || 200);
  } catch (error) {
    console.error("payout settlement failed", error);
    return jsonResponse({ error: "payout_settlement_failed", message: String(error?.message || error) }, 500);
  }
}
