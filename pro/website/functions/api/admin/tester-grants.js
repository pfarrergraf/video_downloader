import { jsonResponse } from "../../_lib.js";
import {
  createTesterGrant,
  isTesterAdmin,
  listTesterGrants,
  revokeTesterGrant,
} from "../../_tester_grants.js";

function unauthorized() {
  return jsonResponse({ error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
}

export async function onRequestGet({ request, env }) {
  if (!env.DB) return jsonResponse({ error: "DB is not configured" }, 500);
  if (!(await isTesterAdmin(request, env))) return unauthorized();
  return jsonResponse({ grants: await listTesterGrants(env) });
}

export async function onRequestPost({ request, env }) {
  if (!env.DB) return jsonResponse({ error: "DB is not configured" }, 500);
  if (!(await isTesterAdmin(request, env))) return unauthorized();
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "invalid JSON" }, 400);
  }

  if (body?.action === "revoke") {
    if (typeof body.id !== "string" || !body.id.trim()) return jsonResponse({ error: "id is required" }, 400);
    const revoked = await revokeTesterGrant(env, body.id.trim());
    return revoked ? jsonResponse({ revoked: true }) : jsonResponse({ error: "grant not found or already revoked" }, 404);
  }

  const label = typeof body?.label === "string" ? body.label.trim() : "";
  const grantType = body?.grant_type === "owner" ? "owner" : body?.grant_type === "tester" ? "tester" : "";
  if (!label || label.length > 120) return jsonResponse({ error: "label must be 1-120 characters" }, 400);
  if (!grantType) return jsonResponse({ error: "grant_type must be owner or tester" }, 400);

  let expiresAt = null;
  if (grantType === "tester") {
    const days = Number(body?.expires_in_days);
    if (!Number.isInteger(days) || days < 1 || days > 3650) {
      return jsonResponse({ error: "tester expires_in_days must be an integer from 1 to 3650" }, 400);
    }
    expiresAt = Math.floor(Date.now() / 1000) + days * 24 * 3600;
  }
  return jsonResponse(await createTesterGrant(env, { label, grantType, expiresAt }), 201);
}
