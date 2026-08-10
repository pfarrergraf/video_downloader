import { jsonResponse } from "../../_lib.js";
import { decidePlayRefund, isRefundAdmin, listPlayRefunds } from "../../_play_refunds.js";
import { grantPlayPurchaseCooldownBypass } from "../../_play_purchase_eligibility.js";

function unauthorized() {
  return jsonResponse({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
}

export async function onRequestGet({ request, env }) {
  if (!(await isRefundAdmin(request, env))) return unauthorized();
  return jsonResponse({ refunds: await listPlayRefunds(env) });
}

export async function onRequestPost({ request, env }) {
  if (!(await isRefundAdmin(request, env))) return unauthorized();
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "invalid JSON" }, 400);
  }
  if (typeof body?.id !== "string" || !["approve", "reject", "grant_test_bypass"].includes(body?.action)) {
    return jsonResponse({ error: "id and action (approve/reject/grant_test_bypass) are required" }, 400);
  }
  try {
    if (body.action === "grant_test_bypass") {
      return jsonResponse(await grantPlayPurchaseCooldownBypass(env, {
        refundRequestId: body.id,
        hours: body.hours ?? 24,
      }));
    }
    return jsonResponse(await decidePlayRefund(env, { id: body.id, approve: body.action === "approve" }));
  } catch (error) {
    return jsonResponse({ error: String(error?.message || error) }, error?.status || 500);
  }
}
