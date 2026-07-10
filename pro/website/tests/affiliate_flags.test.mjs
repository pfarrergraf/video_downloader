import test from "node:test";
import assert from "node:assert/strict";

import {
  affiliateCheckoutEnabled,
  affiliateRegistrationEnabled,
  affiliateRegistrationReady,
} from "../functions/_affiliate_flags.js";

function readyEnv(overrides = {}) {
  return {
    AFFILIATE_REGISTRATION_ENABLED: "true",
    AFFILIATE_CHECKOUT_ENABLED: "false",
    DB: {},
    TURNSTILE_SECRET_KEY: "turnstile-secret",
    TURNSTILE_SITE_KEY: "turnstile-site",
    RESEND_API_KEY: "resend-secret",
    PARTNER_FROM_EMAIL: "DownloadThat <partner@example.test>",
    REFERRAL_HASH_SALT: "01234567890123456789012345678901",
    STRIPE_SECRET_KEY: "stripe-secret",
    STRIPE_WEBHOOK_SECRET: "stripe-webhook-secret",
    STRIPE_PRICE_ID: "price_test",
    ...overrides,
  };
}

test("registration can be enabled while checkout remains disabled", () => {
  const env = readyEnv();
  assert.equal(affiliateRegistrationEnabled(env), true);
  assert.equal(affiliateRegistrationReady(env), true);
  assert.equal(affiliateCheckoutEnabled(env), false);
});

test("checkout requires its own explicit true flag and complete Stripe configuration", () => {
  assert.equal(affiliateCheckoutEnabled(readyEnv({ AFFILIATE_CHECKOUT_ENABLED: "true" })), true);
  assert.equal(affiliateCheckoutEnabled(readyEnv({ AFFILIATE_REGISTRATION_ENABLED: "false", AFFILIATE_CHECKOUT_ENABLED: "true" })), false);
  for (const key of ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID"]) {
    assert.equal(affiliateCheckoutEnabled(readyEnv({ AFFILIATE_CHECKOUT_ENABLED: "true", [key]: "" })), false, key);
  }
});

test("registration fails closed when a required dependency is missing", () => {
  for (const key of [
    "DB",
    "TURNSTILE_SECRET_KEY",
    "TURNSTILE_SITE_KEY",
    "RESEND_API_KEY",
    "PARTNER_FROM_EMAIL",
    "REFERRAL_HASH_SALT",
  ]) {
    assert.equal(affiliateRegistrationReady(readyEnv({ [key]: "" })), false, key);
  }
});

test("legacy AFFILIATE_PROGRAM_ENABLED remains a registration fallback", () => {
  const env = readyEnv({ AFFILIATE_REGISTRATION_ENABLED: undefined, AFFILIATE_PROGRAM_ENABLED: "true" });
  assert.equal(affiliateRegistrationEnabled(env), true);
  assert.equal(affiliateRegistrationReady(env), true);
});
