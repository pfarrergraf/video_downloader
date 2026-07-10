import {
  WITHDRAWAL_TEXT_VERSION,
  affiliateProgramEnabled,
  jsonResponse,
  nowSeconds,
  publicBaseUrl,
  resolveAffiliateAttribution,
} from "../_affiliate.js";

async function createStripeSession(env, body) {
  const response = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams(body),
  });
  if (!response.ok) {
    throw new Error(`Stripe checkout creation failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

export async function onRequestPost({ request, env }) {
  try {
    if (!env.DB || !env.STRIPE_SECRET_KEY || !env.STRIPE_PRICE_ID) {
      return jsonResponse({ error: "not_configured" }, 500);
    }
    if (!affiliateProgramEnabled(env)) {
      return jsonResponse({ error: "affiliate_program_disabled" }, 404);
    }

    const body = await request.json().catch(() => ({}));
    const withdrawalChoice = body.withdrawal_choice === "wait14" ? "wait14" : "waived";
    const attribution = await resolveAffiliateAttribution(request, env, body.partner_code || "");
    if (attribution.error) return jsonResponse({ error: attribution.error }, 400);

    const now = nowSeconds();
    const intentId = crypto.randomUUID();
    const base = publicBaseUrl(request, env);
    const requestedLocale = String(body.locale || "auto");
    const locale = /^[a-z]{2}(?:-[A-Z]{2})?$/.test(requestedLocale) ? requestedLocale : "auto";
    const withdrawalReference = withdrawalChoice === "wait14" ? "wait14" : `waived-${Date.now()}`;

    await env.DB.prepare(
      `INSERT INTO affiliate_checkout_intents
        (id, affiliate_id, click_id, withdrawal_choice, withdrawal_consented_at,
         withdrawal_text_version, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    ).bind(
      intentId,
      attribution.affiliate?.id || null,
      attribution.click?.id || null,
      withdrawalChoice,
      withdrawalChoice === "waived" ? now : null,
      WITHDRAWAL_TEXT_VERSION,
      now,
    ).run();

    const session = await createStripeSession(env, {
      mode: "payment",
      success_url: `${base}/success.html?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${base}/#pricing`,
      locale,
      client_reference_id: withdrawalReference,
      "line_items[0][price]": env.STRIPE_PRICE_ID,
      "line_items[0][quantity]": "1",
      "metadata[tier]": "lifetime",
      "metadata[checkout_intent_id]": intentId,
      "metadata[affiliate_id]": attribution.affiliate?.id || "",
      "metadata[withdrawal_choice]": withdrawalChoice,
      "metadata[withdrawal_text_version]": WITHDRAWAL_TEXT_VERSION,
      "payment_intent_data[metadata][checkout_intent_id]": intentId,
      "payment_intent_data[metadata][affiliate_id]": attribution.affiliate?.id || "",
    });

    await env.DB.prepare(
      `UPDATE affiliate_checkout_intents
          SET stripe_checkout_session_id = ?
        WHERE id = ? AND stripe_checkout_session_id IS NULL`,
    ).bind(session.id, intentId).run();

    return jsonResponse({ url: session.url, session_id: session.id });
  } catch (error) {
    console.error("create-checkout failed", error);
    return jsonResponse({ error: "checkout_failed", message: String(error?.message || error) }, 500);
  }
}
