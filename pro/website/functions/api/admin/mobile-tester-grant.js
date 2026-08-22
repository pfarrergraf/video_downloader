import { jsonResponse, sha256Hex } from "../../_lib.js";
import { createTesterGrant } from "../../_tester_grants.js";

const MAX_TEST_DAYS = 14;
const DEFAULT_TEST_DAYS = 14;
const MOBILE_ADMIN_TOKEN_HASH = "c910e93308ae744955d45219ea264fe9d80e6703409bc1df59666c8c93b5759e";

function response(body, status = 200, extraHeaders = {}) {
  return jsonResponse(body, status, {
    "Cache-Control": "no-store, max-age=0",
    Pragma: "no-cache",
    ...extraHeaders,
  });
}

async function isAuthorized(request) {
  const supplied = (request.headers.get("Authorization") || "")
    .replace(/^Bearer\s+/i, "")
    .trim();
  if (!supplied) return false;
  return (await sha256Hex(supplied)) === MOBILE_ADMIN_TOKEN_HASH;
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return response({ error: "DB is not configured" }, 500);
  if (!(await isAuthorized(request))) {
    return response({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
  }

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
