import { sha256Hex } from "./_lib.js";

function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export async function isTesterAdmin(request, env) {
  const expected = String(env.TESTER_GRANTS_ADMIN_TOKEN || "").trim();
  const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!expected || !supplied) return false;
  return (await sha256Hex(expected)) === (await sha256Hex(supplied));
}

function publicGrant(row) {
  return {
    id: row.id,
    label: row.label,
    grant_type: row.grant_type,
    status: row.status,
    expires_at: row.expires_at,
    created_at: row.created_at,
    updated_at: row.updated_at,
    revoked_at: row.revoked_at,
  };
}

export async function listTesterGrants(env) {
  const rows = await env.DB.prepare(
    `SELECT id, label, grant_type, status, expires_at, created_at, updated_at, revoked_at
     FROM tester_grants ORDER BY created_at DESC`,
  ).all();
  return rows.results.map(publicGrant);
}

export async function createTesterGrant(env, { label, grantType, expiresAt }) {
  const id = crypto.randomUUID();
  const random = new Uint8Array(32);
  crypto.getRandomValues(random);
  const prefix = grantType === "owner" ? "DT-OWNER-" : "DT-TEST-";
  const key = `${prefix}${base64Url(random)}`;
  const now = Math.floor(Date.now() / 1000);
  await env.DB.prepare(
    `INSERT INTO tester_grants
      (id, key_hash, label, grant_type, status, expires_at, created_at, updated_at)
     VALUES (?, ?, ?, ?, 'active', ?, ?, ?)`,
  ).bind(id, await sha256Hex(key), label, grantType, expiresAt, now, now).run();
  return { id, key, label, grant_type: grantType, expires_at: expiresAt, created_at: now };
}

export async function revokeTesterGrant(env, id) {
  const now = Math.floor(Date.now() / 1000);
  const result = await env.DB.prepare(
    `UPDATE tester_grants SET status = 'revoked', revoked_at = ?, updated_at = ?
     WHERE id = ? AND status = 'active'`,
  ).bind(now, now, id).run();
  return Number(result.meta?.changes || 0) === 1;
}
