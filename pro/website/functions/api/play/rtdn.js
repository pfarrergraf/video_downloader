import { jsonResponse } from "../../_lib.js";
import { revokePlayPurchaseByToken, verifyAndApplyPlayPurchase, verifyGoogleOidcJwt } from "../../_google_play.js";

function decodeData(value) {
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(value), (char) => char.charCodeAt(0))));
}

export async function onRequestPost({ request, env }) {
  const authorization = request.headers.get("Authorization") || "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  try {
    if (!match || !(await verifyGoogleOidcJwt(match[1], env, env.OIDC_FETCH || fetch))) {
      return jsonResponse({ error: "invalid Google OIDC token" }, 401);
    }
    const envelope = await request.json();
    const notification = decodeData(envelope?.message?.data || "");
    const expectedPackage = env.PLAY_PACKAGE_NAME || "de.classydl.app";
    if (notification.packageName !== expectedPackage) {
      return jsonResponse({ error: "unexpected package" }, 400);
    }
    if (notification.testNotification) return jsonResponse({ received: true, test: true });
    const oneTime = notification.oneTimeProductNotification;
    if (!oneTime?.purchaseToken || oneTime.sku !== (env.PLAY_PRODUCT_ID || "pro")) {
      return jsonResponse({ error: "unsupported notification" }, 400);
    }
    // notificationType 2 is CANCELED. Revoke immediately: a voided token may
    // already return 404 from the purchase API and must still fail closed.
    if (Number(oneTime.notificationType) === 2) {
      const found = await revokePlayPurchaseByToken(env, oneTime.purchaseToken);
      return jsonResponse({ received: true, revoked: found });
    }
    const result = await verifyAndApplyPlayPurchase(env, oneTime.purchaseToken, {
      packageName: notification.packageName,
      productId: oneTime.sku,
    });
    return jsonResponse({ received: true, entitled: result.entitled, purchase_state: result.state });
  } catch (error) {
    console.error("RTDN processing failed", { message: String(error?.message || error) });
    return jsonResponse({ error: "RTDN processing failed" }, 500);
  }
}
