import { jsonResponse } from "../../../_lib.js";
import { requestPlayRefund } from "../../../_play_refunds.js";

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ ok: false, error: "invalid_json" }, 400);
  }
  try {
    const result = await requestPlayRefund(env, {
      purchaseToken: body?.purchase_token,
      deviceId: body?.device_id,
      reason: body?.reason,
    });
    return jsonResponse({ ok: true, ...result }, result.status === "processing" ? 202 : 200);
  } catch (error) {
    console.error("Play refund request rejected", { message: String(error?.message || error) });
    return jsonResponse({ ok: false, error: "refund_request_rejected" }, error?.status || 500);
  }
}
