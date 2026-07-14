import { jsonResponse } from "../../../_lib.js";
import { verifyAndApplyPlayPurchase } from "../../../_google_play.js";

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "invalid JSON" }, 400);
  }
  try {
    const result = await verifyAndApplyPlayPurchase(env, body?.purchase_token, {
      packageName: body?.package_name,
      productId: body?.product_id,
    });
    return jsonResponse({
      entitled: result.entitled,
      purchase_state: result.state,
      license_key: result.licenseKey,
      acknowledged: result.acknowledged,
      verified_at: result.verifiedAt,
      offline_grace_seconds: result.offlineGraceSeconds,
    });
  } catch (error) {
    console.error("Google Play verification failed", { message: String(error?.message || error) });
    const status = Number(error?.status) || 502;
    return jsonResponse({ error: status < 500 ? error.message : "purchase verification unavailable" }, status);
  }
}
