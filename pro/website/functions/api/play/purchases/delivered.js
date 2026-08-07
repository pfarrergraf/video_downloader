import { jsonResponse } from "../../../_lib.js";
import { markPlayEntitlementDelivered } from "../../../_play_refunds.js";

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ ok: false, error: "invalid_json" }, 400);
  }
  try {
    return jsonResponse({ ok: true, ...(await markPlayEntitlementDelivered(env, {
      purchaseToken: body?.purchase_token,
      deviceId: body?.device_id,
    })) });
  } catch (error) {
    return jsonResponse({ ok: false, error: "delivery_confirmation_rejected" }, error?.status || 500);
  }
}
