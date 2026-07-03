import { jsonResponse, stripeGet, stripePost, stripeDelete } from "../_lib.js";

// Voluntary self-service refund, honored for 14 days after purchase
// regardless of whether the statutory withdrawal right already lapsed via the
// pricing page's consent checkbox (see AGB §6.3) - see datenschutz.html §3.5
// for the data-processing disclosure this implements.
const REFUND_WINDOW_SECONDS = 14 * 24 * 3600;

export async function onRequestPost({ request, env }) {
  try {
    if (!env.STRIPE_SECRET_KEY || !env.DB) {
      return jsonResponse({ error: "not_configured" }, 500);
    }

    const body = await request.json().catch(() => ({}));
    const licenseKey = String(body.license_key || "").trim();
    const email = String(body.email || "").trim().toLowerCase();
    if (!licenseKey || !email) {
      return jsonResponse({ error: "missing_fields" }, 400);
    }

    const row = await env.DB.prepare(`SELECT * FROM licenses WHERE license_key = ?`)
      .bind(licenseKey)
      .first();

    // Same generic response whether the key doesn't exist or the email just
    // doesn't match it - don't let this endpoint be used to probe which
    // license keys exist.
    if (!row || String(row.email || "").toLowerCase() !== email) {
      return jsonResponse({ error: "no_match" }, 404);
    }
    if (row.status === "canceled") {
      return jsonResponse({ error: "already_canceled" }, 400);
    }

    const now = Math.floor(Date.now() / 1000);
    if (now - row.created_at > REFUND_WINDOW_SECONDS) {
      return jsonResponse({ error: "window_expired" }, 400);
    }

    let paymentIntentId = null;

    if (row.tier === "lifetime") {
      const session = await stripeGet(
        `/checkout/sessions/${row.stripe_checkout_session_id}?expand[]=payment_intent`,
        env,
      );
      paymentIntentId = session.payment_intent?.id ?? session.payment_intent ?? null;
    } else if (row.stripe_subscription_id) {
      const session = await stripeGet(`/checkout/sessions/${row.stripe_checkout_session_id}`, env);
      if (session.invoice) {
        const invoice = await stripeGet(`/invoices/${session.invoice}?expand[]=payment_intent`, env);
        paymentIntentId = invoice.payment_intent?.id ?? invoice.payment_intent ?? null;
      }
      // Cancel the subscription immediately so it doesn't renew again while
      // the refund itself is being processed.
      await stripeDelete(`/subscriptions/${row.stripe_subscription_id}`, env).catch((err) => {
        console.error("Subscription cancel during refund failed", row.stripe_subscription_id, err);
      });
    }

    if (paymentIntentId) {
      await stripePost(`/refunds`, env, {
        payment_intent: paymentIntentId,
        reason: "requested_by_customer",
      });
    } else {
      console.error("Refund requested but no payment_intent found", licenseKey);
    }

    await env.DB.prepare(`UPDATE licenses SET status = 'canceled', updated_at = ? WHERE license_key = ?`)
      .bind(now, licenseKey)
      .run();

    return jsonResponse({ refunded: true });
  } catch (err) {
    console.error("Refund handling failed", err);
    return jsonResponse({ error: "handler_error", message: String(err?.message ?? err) }, 500);
  }
}
