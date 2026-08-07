import { jsonResponse, sha256Hex } from "../../_lib.js";
import { reconcilePlayPurchases } from "../../_google_play.js";
import { reconcileVoidedAffiliatePurchases } from "../../_affiliate_reconciliation.js";
import { releaseMatureCommissions } from "../../_affiliate_commissions.js";

export async function onRequestPost({ request, env }) {
  const expected = env.PLAY_RECONCILIATION_SECRET;
  const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!expected || !supplied || (await sha256Hex(supplied)) !== (await sha256Hex(expected))) {
    return jsonResponse({ error: "unauthorized" }, 401);
  }
  let body = {};
  try { body = await request.json(); } catch { /* body is optional for scheduled callers */ }
  return jsonResponse({
    purchases: await reconcilePlayPurchases(env, body.limit),
    affiliate_voided: await reconcileVoidedAffiliatePurchases(env, body.limit),
    affiliate_commissions: await releaseMatureCommissions(env, body.limit),
  });
}
