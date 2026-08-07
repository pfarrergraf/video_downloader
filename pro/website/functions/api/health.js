import { jsonResponse } from "../_lib.js";

export async function onRequestGet({ env }) {
  const playBackendConfigured = env.PLAY_BACKEND_CONFIGURED === "true";
  const checks = {
    dbBindingPresent: Boolean(env.DB),
    playServiceAccountConfigured: Boolean(
      env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL && env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY,
    ),
    tokenEncryptionConfigured: Boolean(env.PLAY_TOKEN_ENCRYPTION_KEY),
    rtdnConfigured: Boolean(env.PLAY_RTDN_AUDIENCE && env.PLAY_RTDN_SERVICE_ACCOUNT_EMAIL),
    refundAdminConfigured: Boolean(env.PLAY_REFUND_ADMIN_TOKEN),
    automatedRefundsEnabled: env.PLAY_AUTOMATED_REFUNDS_ENABLED === "true",
    affiliateEnabled: env.AFFILIATE_ENABLED === "true",
    affiliateRedirectEnabled: env.AFFILIATE_REDIRECT_ENABLED === "true",
    affiliateAttributionEnabled: env.AFFILIATE_ATTRIBUTION_ENABLED === "true",
    affiliateCommissionEnabled: env.AFFILIATE_COMMISSION_ENABLED === "true",
    affiliateAdminEnabled: env.AFFILIATE_ADMIN_ENABLED === "true",
    affiliateSigningConfigured: Boolean(env.AFFILIATE_SIGNING_SECRET),
    affiliateInstallHashConfigured: Boolean(env.AFFILIATE_INSTALL_HASH_SALT),
    affiliateAdminTokenConfigured: Boolean(env.AFFILIATE_ADMIN_TOKEN),
  };
  const backendChecks = [
    checks.playServiceAccountConfigured,
    checks.tokenEncryptionConfigured,
    checks.rtdnConfigured,
  ];
  const affiliateChecks = !checks.affiliateEnabled || (
    checks.affiliateSigningConfigured && checks.affiliateInstallHashConfigured &&
    (!checks.affiliateAdminEnabled || checks.affiliateAdminTokenConfigured)
  );
  const ok = checks.dbBindingPresent && affiliateChecks && (!playBackendConfigured || backendChecks.every(Boolean));
  return jsonResponse(
    { ok, mode: playBackendConfigured ? "play_backend" : "website_only", checks },
    ok ? 200 : 503,
  );
}
