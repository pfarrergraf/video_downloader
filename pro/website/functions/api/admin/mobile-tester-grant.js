import { jsonResponse } from "../../_lib.js";
import { createTesterGrant } from "../../_tester_grants.js";
import { verifyCloudflareAccessAdmin } from "../../_access_admin.js";

const MAX_TEST_DAYS = 14;
const DEFAULT_TEST_DAYS = 14;

function response(body, status = 200) {
  return jsonResponse(body, status, {
    "Cache-Control": "no-store, max-age=0",
    Pragma: "no-cache",
  });
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return response({ error: "DB is not configured" }, 500);

  const auth = await verifyCloudflareAccessAdmin(request, env);
  if (!auth.ok) return response({ error: auth.error }, auth.status);

  let body;
  try {
    body = await request.json();
  } catch {
    return response({ error: "invalid JSON" }, 400);
  }

  const label = typeof body?.label === "string" ? body.label.trim() : "";
  if (!label || label.length > 120) {
    return response({ error: "label must be 1-120 characters" }, 400);
  }

  const requested = body?.expires_in_days == null || body.expires_in_days === ""
    ? DEFAULT_TEST_DAYS
    : Number(body.expires_in_days);
  if (!Number.isInteger(requested) || requested < 1 || requested > MAX_TEST_DAYS) {
    return response({ error: `expires_in_days must be an integer from 1 to ${MAX_TEST_DAYS}` }, 400);
  }

  const expiresAt = Math.floor(Date.now() / 1000) + requested * 24 * 3600;
  const created = await createTesterGrant(env, {
    label,
    grantType: "tester",
    expiresAt,
  });

  return response({
    key: created.key,
    id: created.id,
    label: created.label,
    expires_in_days: requested,
    expires_at: created.expires_at,
  }, 201);
}
