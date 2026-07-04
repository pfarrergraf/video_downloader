// Shared helpers for the /api/* Pages Functions routes. Files/dirs prefixed
// with "_" aren't routed by Cloudflare Pages, so this is a safe place for a
// plain module import.
//
// This used to be a standalone Cloudflare Worker (see git history / pro/worker/)
// deployed separately from the static site. Moved into Pages Functions so the
// whole backend deploys via Cloudflare's git integration alongside the site —
// no wrangler CLI, no separate deploy step, no API token to hand anyone. Also
// means /api/* is same-origin from the website's own JS, so no CORS handling
// is needed here (the Android app's HTTP client doesn't enforce CORS either —
// that's a browser-only mechanism).

export function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Stripe's own recommended tolerance for webhook signature timestamps -
// rejects a captured/replayed request (from logs, a proxy, a debug artifact)
// that would otherwise still pass the HMAC check no matter how old it is.
const WEBHOOK_TOLERANCE_SECONDS = 5 * 60;

// Stripe signs webhooks as header `t=<timestamp>,v1=<hex hmac>` computed over
// `${timestamp}.${payload}` with the endpoint's signing secret.
export async function verifyStripeSignature(payload, header, secret) {
  const parts = Object.fromEntries(header.split(",").map((kv) => kv.split("=")));
  const timestamp = parts.t;
  const expectedSig = parts.v1;
  if (!timestamp || !expectedSig) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - Number(timestamp)) > WEBHOOK_TOLERANCE_SECONDS) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signatureBuffer = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${timestamp}.${payload}`),
  );
  const computedSig = [...new Uint8Array(signatureBuffer)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  if (computedSig.length !== expectedSig.length) return false;
  let diff = 0;
  for (let i = 0; i < computedSig.length; i++) {
    diff |= computedSig.charCodeAt(i) ^ expectedSig.charCodeAt(i);
  }
  return diff === 0;
}

export async function sha256Hex(text) {
  const buffer = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function generateLicenseKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase();
  return `DLT-${hex.slice(0, 8)}-${hex.slice(8, 16)}-${hex.slice(16, 24)}`;
}

async function fetchStripeSubscription(subscriptionId, env) {
  const res = await fetch(`https://api.stripe.com/v1/subscriptions/${subscriptionId}`, {
    headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` },
  });
  if (!res.ok) throw new Error(`Stripe subscription fetch failed: ${res.status}`);
  return res.json();
}

// Generic helpers for refund.js (fetchStripeSubscription above is kept as-is
// rather than rewritten on top of these, to avoid touching the already-working
// webhook path for an unrelated feature).
export async function stripeGet(path, env) {
  const res = await fetch(`https://api.stripe.com/v1${path}`, {
    headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` },
  });
  if (!res.ok) throw new Error(`Stripe GET ${path} failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function stripePost(path, env, body) {
  const res = await fetch(`https://api.stripe.com/v1${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams(body),
  });
  if (!res.ok) throw new Error(`Stripe POST ${path} failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function stripeDelete(path, env) {
  const res = await fetch(`https://api.stripe.com/v1${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` },
  });
  if (!res.ok) throw new Error(`Stripe DELETE ${path} failed: ${res.status} ${await res.text()}`);
  return res.json();
}

async function handleCheckoutCompleted(session, env) {
  const tier = session.metadata?.tier;
  if (!tier || !["monthly", "yearly", "lifetime"].includes(tier)) {
    console.error("checkout.session.completed missing/unknown tier metadata", session.id);
    return { created: false, reason: "missing/unknown tier metadata", session_metadata: session.metadata ?? null };
  }

  // Stripe uses at-least-once webhook delivery and can redeliver this event
  // (e.g. if our response was slow/lost) - without this check a redelivery
  // would mint a second distinct license key for the same single payment.
  const existing = await env.DB.prepare(
    `SELECT license_key FROM licenses WHERE stripe_checkout_session_id = ?`,
  )
    .bind(session.id)
    .first();
  if (existing) {
    return { created: false, reason: "already processed", license_key: existing.license_key };
  }

  const email = session.customer_details?.email ?? session.customer_email ?? "unknown";
  const now = Math.floor(Date.now() / 1000);
  let currentPeriodEnd = null;

  if (session.subscription) {
    const subscription = await fetchStripeSubscription(session.subscription, env);
    currentPeriodEnd = subscription.current_period_end ?? null;
  }

  const licenseKey = generateLicenseKey();

  await env.DB.prepare(
    `INSERT INTO licenses
      (license_key, tier, email, stripe_customer_id, stripe_subscription_id,
       stripe_checkout_session_id, status, current_period_end, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)`,
  )
    .bind(
      licenseKey,
      tier,
      email,
      session.customer ?? null,
      session.subscription ?? null,
      session.id,
      currentPeriodEnd,
      now,
      now,
    )
    .run();

  return { created: true, license_key: licenseKey };
}

// SEPA Direct Debit (and other delayed-notification payment methods) fire
// checkout.session.completed as soon as the customer authorizes the mandate,
// not when the debit actually clears — that can fail days later (e.g.
// insufficient funds). Without this, a bounced SEPA debit would leave a
// license permanently active since nothing else ever revokes it.
async function handleCheckoutAsyncPaymentFailed(session, env) {
  const now = Math.floor(Date.now() / 1000);
  await env.DB.prepare(
    `UPDATE licenses SET status = 'canceled', updated_at = ? WHERE stripe_checkout_session_id = ?`,
  )
    .bind(now, session.id)
    .run();
}

async function handleSubscriptionUpdated(subscription, env) {
  const now = Math.floor(Date.now() / 1000);
  // Mirrors handleSubscriptionDeleted's and refund.js's use of 'canceled' for
  // the same "no longer active" condition - Stripe can send this via an
  // .updated event with status: 'canceled' instead of (or before) a separate
  // .deleted event, and treating it as 'expired' here made an intentional
  // cancellation indistinguishable from a lapsed/unpaid subscription in
  // reporting, even though both are denied the same way by validate.js.
  const status =
    subscription.status === "active" || subscription.status === "trialing"
      ? "active"
      : subscription.status === "canceled"
        ? "canceled"
        : "expired";
  await env.DB.prepare(
    `UPDATE licenses SET status = ?, current_period_end = ?, updated_at = ?
     WHERE stripe_subscription_id = ?`,
  )
    .bind(status, subscription.current_period_end ?? null, now, subscription.id)
    .run();
}

async function handleSubscriptionDeleted(subscription, env) {
  const now = Math.floor(Date.now() / 1000);
  await env.DB.prepare(
    `UPDATE licenses SET status = 'canceled', updated_at = ? WHERE stripe_subscription_id = ?`,
  )
    .bind(now, subscription.id)
    .run();
}

export async function handleStripeEvent(event, env) {
  switch (event.type) {
    case "checkout.session.completed":
      return (await handleCheckoutCompleted(event.data.object, env)) ?? { handled: true };
    case "checkout.session.async_payment_failed":
      await handleCheckoutAsyncPaymentFailed(event.data.object, env);
      return { handled: true };
    case "customer.subscription.updated":
      await handleSubscriptionUpdated(event.data.object, env);
      return { handled: true };
    case "customer.subscription.deleted":
      await handleSubscriptionDeleted(event.data.object, env);
      return { handled: true };
    default:
      return { handled: false, type: event.type };
  }
}
