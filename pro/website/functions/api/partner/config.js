import { jsonResponse } from "../../_affiliate.js";
import {
  affiliateCheckoutEnabled,
  affiliateRegistrationEnabled,
  affiliateRegistrationReady,
} from "../../_affiliate_flags.js";

export async function onRequestGet({ env }) {
  const registrationEnabled = affiliateRegistrationEnabled(env);
  const registrationReady = affiliateRegistrationReady(env);
  return jsonResponse({
    enabled: registrationReady,
    registration_enabled: registrationEnabled,
    registration_ready: registrationReady,
    checkout_enabled: affiliateCheckoutEnabled(env),
    turnstile_site_key: registrationReady ? env.TURNSTILE_SITE_KEY : null,
    payout_minimum_cents: 5000,
    attribution_days: 180,
    review_days: 30,
    commission_tiers: [
      { from: 1, to: 10, cents: 200 },
      { from: 11, to: 50, cents: 250 },
      { from: 51, to: 100, cents: 300 },
      { from: 101, to: 500, cents: 350 },
      { from: 501, to: null, cents: 400 },
    ],
  });
}
