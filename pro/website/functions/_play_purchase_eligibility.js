import { sha256Hex } from "./_lib.js";

const DAY = 24 * 60 * 60;
const COOLDOWN_DAYS = [1, 7, 30, 180];

function nowSeconds(env) {
  const override = Number(env.PLAY_NOW_SECONDS);
  return Number.isFinite(override) ? Math.floor(override) : Math.floor(Date.now() / 1000);
}

function requireDeviceId(deviceId) {
  if (typeof deviceId !== "string" || deviceId.length < 16 || deviceId.length > 256) {
    throw Object.assign(new Error("invalid device id"), { status: 400 });
  }
}

export async function playPurchaseEligibility(env, deviceId) {
  if (!env.DB) throw Object.assign(new Error("DB is not configured"), { status: 500 });
  requireDeviceId(deviceId);
  const deviceHash = await sha256Hex(deviceId);
  const now = nowSeconds(env);
  const bypass = await env.DB.prepare(
    `SELECT expires_at FROM play_purchase_cooldown_bypasses
     WHERE device_id_hash = ? AND expires_at > ?`,
  ).bind(deviceHash, now).first();
  const history = await env.DB.prepare(
    `SELECT COUNT(*) AS refund_count, MAX(refunded_at) AS last_refunded_at
     FROM play_refund_requests WHERE device_id_hash = ? AND status = 'refunded'`,
  ).bind(deviceHash).first();
  const refundCount = Number(history?.refund_count || 0);
  const lastRefundedAt = Number(history?.last_refunded_at || 0);
  const days = refundCount > 0 ? COOLDOWN_DAYS[Math.min(refundCount - 1, COOLDOWN_DAYS.length - 1)] : 0;
  const blockedUntil = lastRefundedAt > 0 ? lastRefundedAt + days * DAY : null;
  const bypassed = Boolean(bypass);
  const eligible = bypassed || blockedUntil == null || now >= blockedUntil;
  return {
    eligible,
    refund_count: refundCount,
    blocked_until: eligible ? null : blockedUntil,
    cooldown_seconds: eligible ? 0 : blockedUntil - now,
    test_bypass_until: bypassed ? Number(bypass.expires_at) : null,
  };
}

export async function grantPlayPurchaseCooldownBypass(env, { refundRequestId, hours = 24 }) {
  if (typeof refundRequestId !== "string" || !refundRequestId) {
    throw Object.assign(new Error("refund request id is required"), { status: 400 });
  }
  const durationHours = Number(hours);
  if (!Number.isInteger(durationHours) || durationHours < 1 || durationHours > 168) {
    throw Object.assign(new Error("hours must be an integer from 1 to 168"), { status: 400 });
  }
  const refund = await env.DB.prepare(
    `SELECT device_id_hash FROM play_refund_requests WHERE id = ? AND status = 'refunded'`,
  ).bind(refundRequestId).first();
  if (!refund) throw Object.assign(new Error("refunded request not found"), { status: 404 });
  const now = nowSeconds(env);
  const expiresAt = now + durationHours * 60 * 60;
  await env.DB.prepare(
    `INSERT INTO play_purchase_cooldown_bypasses
       (device_id_hash, expires_at, source_refund_request_id, reason, created_at, updated_at)
     VALUES (?, ?, ?, 'release_testing', ?, ?)
     ON CONFLICT(device_id_hash) DO UPDATE SET
       expires_at = excluded.expires_at,
       source_refund_request_id = excluded.source_refund_request_id,
       reason = excluded.reason,
       updated_at = excluded.updated_at`,
  ).bind(refund.device_id_hash, expiresAt, refundRequestId, now, now).run();
  return { granted: true, expires_at: expiresAt };
}
