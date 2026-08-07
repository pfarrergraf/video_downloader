import { jsonResponse, sha256Hex } from "../../_lib.js";
import { revokePlayPurchaseByToken, verifyAndApplyPlayPurchase, verifyGoogleOidcJwt } from "../../_google_play.js";
import { affiliateFlags, claimAffiliateEvent, completeAffiliateEvent } from "../../_affiliate.js";
import { voidAffiliatePurchase } from "../../_affiliate_commissions.js";

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
    const affiliateEnabled = affiliateFlags(env).enabled;
    const externalEventId = envelope?.message?.messageId || envelope?.message?.message_id || null;
    let eventClaim = null;
    if (affiliateEnabled && externalEventId) {
      eventClaim = await claimAffiliateEvent(env, {
        source: "google_play_rtdn",
        externalEventId: String(externalEventId),
        eventType: "play_notification",
        payload: notification,
      });
      if (eventClaim.dedupe) return jsonResponse({ received: true, duplicate: true });
    }
    const expectedPackage = env.PLAY_PACKAGE_NAME || "de.classydl.app";
    if (notification.packageName !== expectedPackage) {
      if (eventClaim) await completeAffiliateEvent(env, { source: "google_play_rtdn", externalEventId, status: "rejected" });
      return jsonResponse({ error: "unexpected package" }, 400);
    }
    if (notification.testNotification) {
      if (eventClaim) await completeAffiliateEvent(env, { source: "google_play_rtdn", externalEventId });
      return jsonResponse({ received: true, test: true });
    }
    const voided = notification.voidedPurchaseNotification;
    if (voided?.purchaseToken) {
      const found = await revokePlayPurchaseByToken(env, voided.purchaseToken);
      if (affiliateEnabled) {
        await voidAffiliatePurchase(env, {
          purchaseTokenHash: await sha256Hex(voided.purchaseToken),
          reason: `rtdn_voided_${voided.orderId || "unknown"}`,
        });
      }
      if (eventClaim) await completeAffiliateEvent(env, { source: "google_play_rtdn", externalEventId });
      return jsonResponse({ received: true, revoked: found });
    }
    const oneTime = notification.oneTimeProductNotification;
    if (!oneTime?.purchaseToken || oneTime.sku !== (env.PLAY_PRODUCT_ID || "pro")) {
      if (eventClaim) await completeAffiliateEvent(env, { source: "google_play_rtdn", externalEventId, status: "rejected" });
      return jsonResponse({ error: "unsupported notification" }, 400);
    }
    // notificationType 2 is CANCELED. Revoke immediately: a voided token may
    // already return 404 from the purchase API and must still fail closed.
    if (Number(oneTime.notificationType) === 2) {
      const found = await revokePlayPurchaseByToken(env, oneTime.purchaseToken);
      if (affiliateEnabled) {
        await voidAffiliatePurchase(env, {
          purchaseTokenHash: await sha256Hex(oneTime.purchaseToken),
          reason: "rtdn_cancelled",
        });
      }
      if (eventClaim) await completeAffiliateEvent(env, { source: "google_play_rtdn", externalEventId });
      return jsonResponse({ received: true, revoked: found });
    }
    const result = await verifyAndApplyPlayPurchase(env, oneTime.purchaseToken, {
      packageName: notification.packageName,
      productId: oneTime.sku,
    });
    if (eventClaim) await completeAffiliateEvent(env, { source: "google_play_rtdn", externalEventId });
    return jsonResponse({ received: true, entitled: result.entitled, purchase_state: result.state });
  } catch (error) {
    // A non-2xx response asks Pub/Sub to retry. Persisting retryable status lets
    // the next delivery reclaim the event without losing its dedupe key.
    console.error("RTDN processing failed", { message: String(error?.message || error) });
    return jsonResponse({ error: "RTDN processing failed" }, 500);
  }
}
