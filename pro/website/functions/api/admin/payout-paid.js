import {
  getAffiliateSession,
  jsonResponse,
  markAffiliatePayoutPaid,
  normalizeEmail,
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
    const payoutId = String(body.payout_id || "");
    const externalReference = String(body.external_reference || "").trim();
    if (!payoutId) return jsonResponse({ error: "payout_id_required" }, 400);
    const actor = `admin:${normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)}`;

    await runReconciliation(env, actor);
    await requireLockedIntegrityForPayout(env, actor);
    const result = await markAffiliatePayoutPaid(env, payoutId, actor, externalReference);
    const httpStatus = typeof result.status === "number" ? result.status : 200;
    if (result.error) return jsonResponse(result, httpStatus);

    const postCheck = await runLockedIntegrityGate(env, actor);
    if (postCheck.status !== "ok") {
      return jsonResponse({
        error: "post_settlement_integrity_failure",
        payout_recorded: result,
        integrity: postCheck,
      }, 409);
    }
    return jsonResponse({ ...result, integrity_check_id: postCheck.id }, 200);
  } catch (error) {
    console.error("payout settlement failed", error);
    const status = ["payouts_frozen", "integrity_check_busy"].includes(error.code) ? 409 : 500;
    return jsonResponse({
      error: error.code || "payout_settlement_failed",
      message: String(error?.message || error),
      integrity: error.integrity || undefined,
    }, status);
  }
}
