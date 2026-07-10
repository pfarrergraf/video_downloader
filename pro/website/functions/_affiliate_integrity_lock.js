import { nowSeconds, randomToken } from "./_affiliate.js";
import { runIntegrityGate } from "./_affiliate_integrity.js";

async function acquireIntegrityLease(env) {
  const now = nowSeconds();
  const token = randomToken(16);
  const result = await env.DB.prepare(
    `UPDATE affiliate_controls
        SET integrity_lock_token = ?, integrity_lock_until = ?, updated_at = ?
      WHERE id = 'global'
        AND (integrity_lock_until IS NULL OR integrity_lock_until < ?)`,
  ).bind(token, now + 10 * 60, now, now).run();
  if ((result.meta?.changes || 0) !== 1) {
    const error = new Error("An affiliate integrity check is already running");
    error.code = "integrity_check_busy";
    throw error;
  }
  return token;
}

async function releaseIntegrityLease(env, token) {
  await env.DB.prepare(
    `UPDATE affiliate_controls
        SET integrity_lock_token = NULL, integrity_lock_until = NULL, updated_at = ?
      WHERE id = 'global' AND integrity_lock_token = ?`,
  ).bind(nowSeconds(), token).run();
}

export async function runLockedIntegrityGate(env, actor = "system") {
  const lease = await acquireIntegrityLease(env);
  try {
    return await runIntegrityGate(env, actor);
  } finally {
    await releaseIntegrityLease(env, lease);
  }
}

export async function requireLockedIntegrityForPayout(env, actor) {
  const result = await runLockedIntegrityGate(env, actor);
  if (result.status !== "ok") {
    const error = new Error("Affiliate payout integrity gate is blocked");
    error.code = "payouts_frozen";
    error.integrity = result;
    throw error;
  }
  return result;
}
