import { jsonResponse, stripeGet, stripePost, stripeDelete } from "../_lib.js";

// Voluntary self-service refund, honored for 14 days after purchase
// regardless of whether the statutory withdrawal right already lapsed via the
// pricing page's consent checkbox (see AGB §6.3) - see datenschutz.html §3.5
// for the data-processing disclosure this implements.
const REFUND_WINDOW_SECONDS = 14 * 24 * 3600;

// license_key is unguessable (96 bits of randomness), but a leaked key still
// only needs a matching email to self-serve-cancel someone else's
// subscription - this bounds how many email guesses/requests one IP can make
// against this endpoint regardless of which license_key they're trying.
const RATE_LIMIT_WINDOW_SECONDS = 15 * 60;
const RATE_LIMIT_MAX_ATTEMPTS = 5;

export async function onRequestPost({ request, env }) {
  try {
    if (!env.STRIPE_SECRET_KEY || !env.DB) {
      return jsonResponse({ error: "not_configured" }, 500);
    }

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Math.floor(Date.now() / 1000);
    const windowStart = now - RATE_LIMIT_WINDOW_SECONDS;

    // Opportunistic cleanup instead of a separate cron job - traffic here is
    // low enough that this table was never going to grow unbounded anyway.
    await env.DB.prepare(`DELETE FROM refund_attempts WHERE attempted_at < ?`).bind(windowStart).run();
    const attempts = await env.DB.prepare(
      `SELECT COUNT(*) as count FROM refund_attempts WHERE ip = ? AND attempted_at >= ?`,
    )
      .bind(ip, windowStart)
      .first();
    if ((attempts?.count ?? 0) >= RATE_LIMIT_MAX_ATTEMPTS) {
      return jsonResponse({ error: "rate_limited" }, 429);
    }
    await env.DB.prepare(`INSERT INTO refund_attempts (ip, attempted_at) VALUES (?, ?)`).bind(ip, now).run();

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
      // the refund itself is being processed. If this fails, bail out entirely
      // rather than refunding+revoking anyway - otherwise the customer loses
      // their license while Stripe keeps billing the still-active subscription.
      try {
        await stripeDelete(`/subscriptions/${row.stripe_subscription_id}`, env);
      } catch (err) {
        console.error("Subscription cancel during refund failed", row.stripe_subscription_id, err);
        return jsonResponse({ error: "subscription_cancel_failed" }, 502);
      }
    }

    // No payment_intent means we can't actually refund anything - don't tell
    // the customer they were refunded and revoke their license for nothing.
    if (!paymentIntentId) {
      console.error("Refund requested but no payment_intent found", licenseKey);
      return jsonResponse({ error: "payment_not_found" }, 502);
    }

    await stripePost(`/refunds`, env, {
      payment_intent: paymentIntentId,
      reason: "requested_by_customer",
    });

    await env.DB.prepare(`UPDATE licenses SET status = 'canceled', updated_at = ? WHERE license_key = ?`)
      .bind(now, licenseKey)
      .run();

    return jsonResponse({ refunded: true });
  } catch (err) {
    console.error("Refund handling failed", err);
    return jsonResponse({ error: "handler_error", message: String(err?.message ?? err) }, 500);
  }
}
