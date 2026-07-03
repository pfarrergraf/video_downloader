// Health check endpoint for Cloudflare Pages deployment validation.
// Returns which required bindings and secrets are present WITHOUT revealing
// their values. Safe to call after deployment to verify configuration.
//
// Expected response on a correctly configured deployment:
// {
//   "ok": true,
//   "dbBindingPresent": true,
//   "stripeSecretConfigured": true,
//   "webhookSecretConfigured": true
// }

export async function onRequestGet(context) {
  const { env } = context;

  const dbBindingPresent = typeof env.DB !== "undefined" && env.DB !== null;
  const stripeSecretConfigured =
    typeof env.STRIPE_SECRET_KEY === "string" &&
    env.STRIPE_SECRET_KEY.length > 0;
  const webhookSecretConfigured =
    typeof env.STRIPE_WEBHOOK_SECRET === "string" &&
    env.STRIPE_WEBHOOK_SECRET.length > 0;

  const ok = dbBindingPresent && stripeSecretConfigured;

  return new Response(
    JSON.stringify(
      {
        ok,
        dbBindingPresent,
        stripeSecretConfigured,
        webhookSecretConfigured,
      },
      null,
      2
    ),
    {
      status: ok ? 200 : 503,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    }
  );
}
