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
    const sessionId = String(body.session_id || "").trim();
    const email = String(body.email || "").trim().toLowerCase();
    if (!email || (!licenseKey && !sessionId)) {
      return jsonResponse({ error: "missing_fields" }, 400);
    }

    const row = licenseKey
      ? await env.DB.prepare(`SELECT * FROM licenses WHERE license_key = ?`).bind(licenseKey).first()
      : await env.DB.prepare(`SELECT * FROM licenses WHERE stripe_checkout_session_id = ?`).bind(sessionId).first();

    if (row) {
      // Same generic response whether the key doesn't exist or the email just
      // doesn't match it - don't let this endpoint be used to probe which
      // license keys exist.
      if (String(row.email || "").toLowerCase() !== email) {
        return jsonResponse({ error: "no_match" }, 404);
      }
      if (row.status === "canceled") {
        return jsonResponse({ error: "already_canceled" }, 400);
      }
      if (now - row.created_at > REFUND_WINDOW_SECONDS) {
        return jsonResponse({ error: "window_expired" }, 400);
      }

      const result = await refundCheckoutSession(row.stripe_checkout_session_id, row.stripe_subscription_id, env);
      if (result.error) return jsonResponse({ error: result.error }, result.status);

      await env.DB.prepare(`UPDATE licenses SET status = 'canceled', updated_at = ? WHERE license_key = ?`)
        .bind(now, row.license_key)
        .run();

      return jsonResponse({ refunded: true });
    }

    // No license row - either a bad license_key (already handled above,
    // since that only reaches here via session_id) or a checkout session
    // whose webhook never produced a license (e.g. a duplicate/abandoned
    // purchase attempt). session_id is Stripe's own long random ID, only
    // ever seen by the actual purchaser (success-page URL / receipt) - an
    // equally unguessable credential to license_key, so it's safe to accept
    // as proof of purchase on its own without one.
    if (!sessionId) {
      return jsonResponse({ error: "no_match" }, 404);
    }

    let session;
    try {
      session = await stripeGet(`/checkout/sessions/${sessionId}?expand[]=payment_intent`, env);
    } catch (err) {
      return jsonResponse({ error: "no_match" }, 404);
    }

    const sessionEmail = String(session.customer_details?.email ?? session.customer_email ?? "").toLowerCase();
    if (!sessionEmail || sessionEmail !== email) {
      return jsonResponse({ error: "no_match" }, 404);
    }
    if (now - session.created > REFUND_WINDOW_SECONDS) {
      return jsonResponse({ error: "window_expired" }, 400);
    }

    const result = await refundCheckoutSession(session.id, session.subscription, env, session);
    if (result.error) return jsonResponse({ error: result.error }, result.status);

    return jsonResponse({ refunded: true });
  } catch (err) {
    console.error("Refund handling failed", err);
    return jsonResponse({ error: "handler_error", message: String(err?.message ?? err) }, 500);
  }
}

// Resolves and refunds the PaymentIntent behind a checkout session, canceling
// its subscription first (if any) so it doesn't renew again while the refund
// is pending. Shared by the license_key path above (which hasn't fetched the
// session yet) and the session_id path (which already has, to check the
// email match, and passes it as `prefetchedSession` to avoid a second call).
async function refundCheckoutSession(checkoutSessionId, subscriptionId, env, prefetchedSession = null) {
  const session =
    prefetchedSession ?? (await stripeGet(`/checkout/sessions/${checkoutSessionId}?expand[]=payment_intent`, env));

  let paymentIntent = session.payment_intent && typeof session.payment_intent === "object" ? session.payment_intent : null;
  let paymentIntentId = paymentIntent?.id ?? session.payment_intent ?? null;

  if (subscriptionId) {
    if (session.invoice) {
      const invoice = await stripeGet(`/invoices/${session.invoice}?expand[]=payment_intent`, env);
      paymentIntent =
        invoice.payment_intent && typeof invoice.payment_intent === "object" ? invoice.payment_intent : paymentIntent;
      paymentIntentId = paymentIntent?.id ?? invoice.payment_intent ?? paymentIntentId;
    }

    // Cancel the subscription immediately so it doesn't renew again while
    // the refund itself is being processed. Tolerate it already being
    // canceled - e.g. a retry of this same request after an earlier attempt
    // got as far as canceling the subscription but couldn't refund yet
    // (payment still processing, see below) - rather than failing the whole
    // request on a "no such subscription"/"already canceled" error. Only a
    // genuine cancel failure should block the refund.
    try {
      const subscription = await stripeGet(`/subscriptions/${subscriptionId}`, env);
      if (subscription.status !== "canceled") {
        await stripeDelete(`/subscriptions/${subscriptionId}`, env);
      }
    } catch (err) {
      console.error("Subscription cancel during refund failed", subscriptionId, err);
      return { error: "subscription_cancel_failed", status: 502 };
    }
  }

  // No payment_intent means we can't actually refund anything - don't tell
  // the customer they were refunded and revoke their license for nothing.
  if (!paymentIntentId) {
    console.error("Refund requested but no payment_intent found", checkoutSessionId);
    return { error: "payment_not_found", status: 502 };
  }

  // SEPA Direct Debit (and other delayed-notification methods) leave the
  // PaymentIntent in "processing" for days after checkout - Stripe rejects a
  // refund on anything but a succeeded payment intent, dashboard approval or
  // not. Surface that plainly instead of a confusing generic error; the
  // subscription (if any) is already canceled above so nothing renews while
  // the customer waits and retries this same request once it clears.
  if (paymentIntent && paymentIntent.status !== "succeeded") {
    return { error: "payment_processing", status: 409 };
  }

  await stripePost(`/refunds`, env, {
    payment_intent: paymentIntentId,
    reason: "requested_by_customer",
  });

  return {};
}
