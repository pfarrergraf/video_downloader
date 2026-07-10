import { jsonResponse, verifyStripeSignature, handleStripeEvent } from "../_lib.js";
import { affiliateProgramEnabled } from "../_affiliate.js";
import {
  handleAffiliateChargeRefunded,
  handleAffiliateDisputeClosed,
  handleAffiliateDisputeCreated,
  handleAffiliatePaymentFailure,
  postProcessAffiliateCheckout,
} from "../_affiliate_events.js";

async function handleAffiliateEvent(event, baseResult, env) {
  if (!affiliateProgramEnabled(env)) return { handled: false, reason: "affiliate program disabled" };
  switch (event.type) {
    case "checkout.session.completed":
    case "checkout.session.async_payment_succeeded":
      return postProcessAffiliateCheckout(event.data.object, baseResult?.license_key, env);
    case "checkout.session.async_payment_failed":
      return handleAffiliatePaymentFailure(event.data.object, env);
    case "charge.refunded":
      return handleAffiliateChargeRefunded(event.data.object, env);
    case "charge.dispute.created":
      return handleAffiliateDisputeCreated(event.data.object, env);
    case "charge.dispute.closed":
      return handleAffiliateDisputeClosed(event.data.object, env);
    default:
      return { handled: false, type: event.type };
  }
}

// Signature verification happens before either the license or affiliate handler.
// Stripe retries non-2xx deliveries, while every write path is idempotent.
export async function onRequestPost({ request, env }) {
  try {
    if (!env.STRIPE_WEBHOOK_SECRET) {
      return jsonResponse({ error: "STRIPE_WEBHOOK_SECRET is not configured" }, 500);
    }
    if (!env.DB) {
      return jsonResponse({ error: "DB (D1) binding is not configured" }, 500);
    }

    const signatureHeader = request.headers.get("Stripe-Signature");
    const payload = await request.text();
    if (!signatureHeader || !(await verifyStripeSignature(payload, signatureHeader, env.STRIPE_WEBHOOK_SECRET))) {
      return jsonResponse({ error: "invalid signature" }, 400);
    }

    const event = JSON.parse(payload);
    const result = await handleStripeEvent(event, env);
    const affiliate = await handleAffiliateEvent(event, result, env);
    return jsonResponse({ received: true, result, affiliate });
  } catch (err) {
    console.error("Webhook handling failed", err);
    return jsonResponse({ error: "handler error", message: String(err?.message ?? err), stack: err?.stack }, 500);
  }
}
