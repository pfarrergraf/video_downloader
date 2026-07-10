import {
  approveAffiliatePayout,
  getAffiliateSession,
  jsonResponse,
  normalizeEmail,
  runReconciliation,
} from "../../_affiliate.js";
import { requireIntegrityForPayout, runIntegrityGate } from "../../_affiliate_integrity.js";

export async function onRequestPost({ request, env }) {
  try {
    const session = await getAffiliateSession(request, env, "admin");
    if (!session) return jsonResponse({ error: "unauthorized" }, 401);
    const body = await request.json().catch(() => ({}));
    const payoutId = String(body.payout_id || "");
    if (!payoutId) return jsonResponse({ error: "payout_id_required" }, 400);
    const actor = `admin:${normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)}`;

    await runReconciliation(env, actor);
    await requireIntegrityForPayout(env, actor);
    const result = await approveAffiliatePayout(env, payoutId, actor);
    const httpStatus = typeof result.status === "number" ? result.status : 200;
    if (result.error) return jsonResponse(result, httpStatus);

    const postCheck = await runIntegrityGate(env, actor);
    if (postCheck.status !== "ok") {
      return jsonResponse({ error: "post_approval_integrity_failure", payout: result, integrity: postCheck }, 409);
    }
    return jsonResponse({ ...result, integrity_check_id: postCheck.id }, 200);
  } catch (error) {
    console.error("payout approval failed", error);
    const status = error.code === "payouts_frozen" ? 409 : 500;
    return jsonResponse({
      error: error.code || "payout_approval_failed",
      message: String(error?.message || error),
      integrity: error.integrity || undefined,
    }, status);
  }
}
