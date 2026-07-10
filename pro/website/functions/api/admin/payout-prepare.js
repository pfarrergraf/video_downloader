import {
  getAffiliateSession,
  jsonResponse,
  prepareAffiliatePayout,
  runReconciliation,
} from "../../_affiliate.js";
import {
  requireLockedIntegrityForPayout,
  runLockedIntegrityGate,
} from "../../_affiliate_integrity_lock.js";

export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);
    const body = await request.json().catch(() => ({}));
    const affiliateId = String(body.affiliate_id || "");
    if (!affiliateId) return jsonResponse({ error: "affiliate_id_required" }, 400);

    const actor = "system-payout-engine";
    await runReconciliation(env, actor);
    await requireLockedIntegrityForPayout(env, actor);
    const result = await prepareAffiliatePayout(env, affiliateId, actor);
    const httpStatus = typeof result.status === "number" ? result.status : 200;
    if (result.error) return jsonResponse(result, httpStatus);

    const postCheck = await runLockedIntegrityGate(env, actor);
    if (postCheck.status !== "ok") {
      await env.DB.prepare(
        `UPDATE affiliate_payouts SET status = 'blocked', updated_at = ? WHERE id = ? AND status = 'prepared'`,
      ).bind(Math.floor(Date.now() / 1000), result.payout_id).run();
      return jsonResponse({ error: "post_prepare_integrity_failure", payout: result, integrity: postCheck }, 409);
    }
    return jsonResponse({ ...result, integrity_check_id: postCheck.id }, 200);
  } catch (error) {
    console.error("payout preparation failed", error);
    const status = ["payouts_frozen", "integrity_check_busy"].includes(error.code) ? 409 : 500;
    return jsonResponse({
      error: error.code || "payout_preparation_failed",
      message: String(error?.message || error),
      integrity: error.integrity || undefined,
    }, status);
  }
}
