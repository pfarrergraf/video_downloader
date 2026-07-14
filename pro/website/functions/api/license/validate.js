import { jsonResponse } from "../../_lib.js";
import { validateLicense } from "../../_license_validation.js";

export async function onRequestPost({ request, env }) {
  if (!env.DB) return jsonResponse({ valid: false, error: "DB is not configured" }, 500);
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ valid: false, error: "invalid JSON" }, 400);
  }
  if (!body?.key || typeof body.key !== "string") {
    return jsonResponse({ valid: false, error: "missing key" }, 400);
  }
  return jsonResponse(await validateLicense(env, {
    key: body.key,
    platform: body.platform,
    deviceId: body.device_id,
    appVersion: body.app_version,
  }));
}
