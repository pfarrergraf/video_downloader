function enabled(value) {
  return String(value || "").toLowerCase() === "true";
}

export function affiliateRegistrationEnabled(env) {
  const configured = env.AFFILIATE_REGISTRATION_ENABLED ?? env.AFFILIATE_PROGRAM_ENABLED;
  return enabled(configured);
}

export function affiliateRegistrationReady(env) {
  return Boolean(
    affiliateRegistrationEnabled(env)
      && env.DB
      && env.TURNSTILE_SECRET_KEY
      && env.TURNSTILE_SITE_KEY
      && env.RESEND_API_KEY
      && env.PARTNER_FROM_EMAIL
      && env.REFERRAL_HASH_SALT,
  );
}

export function affiliateCheckoutEnabled(env) {
  return Boolean(
    affiliateRegistrationReady(env)
      && enabled(env.AFFILIATE_CHECKOUT_ENABLED)
      && env.STRIPE_SECRET_KEY
      && env.STRIPE_WEBHOOK_SECRET
      && env.STRIPE_PRICE_ID,
  );
}
