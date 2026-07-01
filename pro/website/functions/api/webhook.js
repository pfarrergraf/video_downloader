import { jsonResponse, verifyStripeSignature, handleStripeEvent } from "../_lib.js";

export async function onRequestPost({ request, env }) {
  const signatureHeader = request.headers.get("Stripe-Signature");
  const payload = await request.text();

  if (!signatureHeader || !(await verifyStripeSignature(payload, signatureHeader, env.STRIPE_WEBHOOK_SECRET))) {
    return jsonResponse({ error: "invalid signature" }, 400);
  }

  const event = JSON.parse(payload);

  try {
    await handleStripeEvent(event, env);
  } catch (err) {
    console.error("Webhook handling failed", err);
    return jsonResponse({ error: "handler error" }, 500);
  }

  return jsonResponse({ received: true });
}
