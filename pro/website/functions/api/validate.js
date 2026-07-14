import { jsonResponse } from "../_lib.js";
import { validateLicense } from "../_license_validation.js";

// Compatibility endpoint for already shipped clients. New clients must use
// POST /api/license/validate so license keys do not leak through URLs/logs.
export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const key = url.searchParams.get("key");
  if (!key) return jsonResponse({ valid: false, error: "missing key" }, 400);
  const response = jsonResponse(await validateLicense(env, {
    key,
    platform: url.searchParams.get("platform"),
    deviceId: url.searchParams.get("device_id"),
    appVersion: url.searchParams.get("app_version"),
  }));
  response.headers.set("Deprecation", "true");
  response.headers.set("Sunset", "Wed, 14 Jul 2027 00:00:00 GMT");
  response.headers.set("Link", '</api/license/validate>; rel="successor-version"');
  return response;
}
