import { jsonResponse } from "../_lib.js";

export async function onRequestGet({ env }) {
  const checks = {
    dbBindingPresent: Boolean(env.DB),
    playServiceAccountConfigured: Boolean(
      env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL && env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY,
    ),
    tokenEncryptionConfigured: Boolean(env.PLAY_TOKEN_ENCRYPTION_KEY),
    rtdnConfigured: Boolean(env.PLAY_RTDN_AUDIENCE && env.PLAY_RTDN_SERVICE_ACCOUNT_EMAIL),
  };
  return jsonResponse({ ok: Object.values(checks).every(Boolean), checks }, Object.values(checks).every(Boolean) ? 200 : 503);
}
