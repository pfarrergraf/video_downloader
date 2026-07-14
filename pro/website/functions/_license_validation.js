import { sha256Hex } from "./_lib.js";

const STALE_SLOT_SECONDS = 90 * 24 * 3600;
const PLAY_OFFLINE_GRACE_SECONDS = 72 * 3600;

export async function validateLicense(env, { key, platform, deviceId, appVersion }) {
  const row = await env.DB.prepare(
    `SELECT l.tier, l.status, l.current_period_end, l.deliver_at,
            p.verified_at AS play_verified_at, p.purchase_state AS play_purchase_state
     FROM licenses l
     LEFT JOIN play_purchases p ON p.license_key = l.license_key
     WHERE l.license_key = ?`,
  ).bind(key).first();
  if (!row) return { valid: false };

  const now = Math.floor(Date.now() / 1000);
  if (row.deliver_at != null && row.deliver_at > now) {
    return { valid: false, status: "pending_delivery", deliver_at: row.deliver_at };
  }
  const expired =
    row.status !== "active" ||
    (row.tier !== "lifetime" && row.current_period_end !== null && row.current_period_end < now) ||
    (row.play_purchase_state != null && row.play_purchase_state !== "purchased");
  const valid = !expired;
  let deviceAllowed = true;
  if (valid && platform && deviceId) {
    deviceAllowed = await checkDeviceSlot(env, key, platform, deviceId, appVersion || null, now);
  }
  const result = {
    valid,
    tier: row.tier,
    status: expired ? "expired" : row.status,
    device_allowed: deviceAllowed,
  };
  if (row.play_verified_at != null) {
    result.provider = "google_play";
    result.verified_at = row.play_verified_at;
    result.offline_grace_until = row.play_verified_at + PLAY_OFFLINE_GRACE_SECONDS;
  }
  return result;
}

async function checkDeviceSlot(env, key, platform, deviceId, appVersion, now) {
  const keyHash = await sha256Hex(key);
  const deviceHash = await sha256Hex(deviceId);
  const existing = await env.DB.prepare(
    `SELECT id FROM license_activations
     WHERE license_key_hash = ? AND platform = ? AND device_id_hash = ? AND revoked_at IS NULL`,
  ).bind(keyHash, platform, deviceHash).first();
  if (existing) {
    await env.DB.prepare(`UPDATE license_activations SET last_seen = ?, app_version = ? WHERE id = ?`)
      .bind(now, appVersion, existing.id).run();
    return true;
  }
  const other = await env.DB.prepare(
    `SELECT id, last_seen FROM license_activations
     WHERE license_key_hash = ? AND platform = ? AND revoked_at IS NULL`,
  ).bind(keyHash, platform).first();
  if (other) {
    if (now - other.last_seen < STALE_SLOT_SECONDS) return false;
    await env.DB.prepare(`UPDATE license_activations SET revoked_at = ? WHERE id = ?`).bind(now, other.id).run();
  }
  await env.DB.prepare(
    `INSERT INTO license_activations
      (license_key_hash, platform, device_id_hash, first_seen, last_seen, app_version)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).bind(keyHash, platform, deviceHash, now, now, appVersion).run();
  return true;
}
