import { jsonResponse, verifyStripeSignature, handleStripeEvent } from "../_lib.js";

// Everything in here used to only be try/caught around handleStripeEvent -
// an exception anywhere else (signature check, JSON.parse, a missing DB/
// secret binding) escaped uncaught and surfaced to Stripe as Cloudflare's
// own generic "error code: 1101" page instead of a diagnosable response.
// Wrapping the whole handler fixes that and lets us see the real cause.
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

    return jsonResponse({ received: true, result });
  } catch (err) {
    console.error("Webhook handling failed", err);
    return jsonResponse({ error: "handler error", message: String(err?.message ?? err), stack: err?.stack }, 500);
  }
}
