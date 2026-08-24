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
  };
  const backendChecks = [
    checks.playServiceAccountConfigured,
    checks.tokenEncryptionConfigured,
    checks.rtdnConfigured,
  ];
  const ok = checks.dbBindingPresent && (!playBackendConfigured || backendChecks.every(Boolean));
  return jsonResponse(
    { ok, mode: playBackendConfigured ? "play_backend" : "website_only", checks },
    ok ? 200 : 503,
  );
}
