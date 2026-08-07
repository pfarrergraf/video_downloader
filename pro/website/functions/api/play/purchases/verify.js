import { jsonResponse, sha256Hex } from "../../../_lib.js";
import { verifyAndApplyPlayPurchase } from "../../../_google_play.js";
import { affiliateFlags } from "../../../_affiliate.js";
import { attributeVerifiedPurchase } from "../../../_affiliate_commissions.js";

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
      deviceId: body?.device_id,
    });
    if (result.entitled && typeof body?.device_id === "string" && body.device_id.length >= 16 && body.device_id.length <= 256) {
      const [tokenHash, deviceHash] = await Promise.all([
        sha256Hex(body.purchase_token),
        sha256Hex(body.device_id),
      ]);
      await env.DB.prepare(
        `UPDATE play_purchases SET purchase_device_id_hash = COALESCE(purchase_device_id_hash, ?)
         WHERE token_hash = ? AND purchase_state = 'purchased'`,
      ).bind(deviceHash, tokenHash).run();
      if (affiliateFlags(env).commission) {
        try {
          await attributeVerifiedPurchase(env, { deviceId: body.device_id, purchaseToken: body.purchase_token });
        } catch (affiliateError) {
          // Attribution must never turn a successful Play verification into an
          // entitlement failure. The next first-start/resume or reconciliation
          // pass can retry it; logs contain no token or device value.
          console.error("Affiliate purchase attribution deferred", {
            message: String(affiliateError?.message || affiliateError),
          });
        }
      }
    }
    return jsonResponse({
      entitled: result.entitled,
      purchase_state: result.state,
      revoked: result.state === "revoked",
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
