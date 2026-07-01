// DownloadThat Pro — license server.
//
// Verifies Stripe webhooks itself via Web Crypto (HMAC-SHA256) instead of the
// Stripe Node SDK, which needs `nodejs_compat` in Workers — this keeps the
// Worker dependency-free. Issues a license key on checkout.session.completed,
// keeps subscription status in sync, and exposes a validation endpoint the
// Android app calls.

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }
    if (request.method === "GET" && url.pathname === "/") {
      return jsonResponse({ status: "ok" });
    }
    if (request.method === "POST" && url.pathname === "/webhook") {
      return handleStripeWebhook(request, env);
    }
    if (request.method === "GET" && url.pathname === "/api/validate") {
      return handleValidate(url, env);
    }
    if (request.method === "GET" && url.pathname === "/api/license-for-session") {
      return handleLicenseForSession(url, env);
    }
    return jsonResponse({ error: "not found" }, 404);
  },
};

// Stripe signs webhooks as header `t=<timestamp>,v1=<hex hmac>` computed over
// `${timestamp}.${payload}` with the endpoint's signing secret.
async function verifyStripeSignature(payload, header, secret) {
  const parts = Object.fromEntries(header.split(",").map((kv) => kv.split("=")));
  const timestamp = parts.t;
  const expectedSig = parts.v1;
  if (!timestamp || !expectedSig) return false;

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

function generateLicenseKey() {
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

async function handleStripeWebhook(request, env) {
  const signatureHeader = request.headers.get("Stripe-Signature");
  const payload = await request.text();

  if (!signatureHeader || !(await verifyStripeSignature(payload, signatureHeader, env.STRIPE_WEBHOOK_SECRET))) {
    return jsonResponse({ error: "invalid signature" }, 400);
  }

  const event = JSON.parse(payload);

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutCompleted(event.data.object, env);
        break;
      case "customer.subscription.updated":
        await handleSubscriptionUpdated(event.data.object, env);
        break;
      case "customer.subscription.deleted":
        await handleSubscriptionDeleted(event.data.object, env);
        break;
      default:
        break;
    }
  } catch (err) {
    console.error("Webhook handling failed", err);
    return jsonResponse({ error: "handler error" }, 500);
  }

  return jsonResponse({ received: true });
}

async function handleCheckoutCompleted(session, env) {
  const tier = session.metadata?.tier;
  if (!tier || !["monthly", "yearly", "lifetime"].includes(tier)) {
    console.error("checkout.session.completed missing/unknown tier metadata", session.id);
    return;
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
}

async function handleSubscriptionUpdated(subscription, env) {
  const now = Math.floor(Date.now() / 1000);
  const status = subscription.status === "active" || subscription.status === "trialing" ? "active" : "expired";
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

async function handleValidate(url, env) {
  const key = url.searchParams.get("key");
  if (!key) return jsonResponse({ valid: false, error: "missing key" }, 400);

  const row = await env.DB.prepare(
    `SELECT tier, status, current_period_end FROM licenses WHERE license_key = ?`,
  )
    .bind(key)
    .first();

  if (!row) return jsonResponse({ valid: false });

  const now = Math.floor(Date.now() / 1000);
  const expired =
    row.status !== "active" ||
    (row.tier !== "lifetime" && row.current_period_end !== null && row.current_period_end < now);

  return jsonResponse({
    valid: !expired,
    tier: row.tier,
    status: expired ? "expired" : row.status,
  });
}

async function handleLicenseForSession(url, env) {
  const sessionId = url.searchParams.get("session_id");
  if (!sessionId) return jsonResponse({ found: false, error: "missing session_id" }, 400);

  const row = await env.DB.prepare(
    `SELECT license_key, tier FROM licenses WHERE stripe_checkout_session_id = ?`,
  )
    .bind(sessionId)
    .first();

  if (!row) return jsonResponse({ found: false });
  return jsonResponse({ found: true, license_key: row.license_key, tier: row.tier });
}
