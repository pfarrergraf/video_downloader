import { jsonResponse, sha256Hex } from "../_lib.js";

// A device that hasn't checked in for this long is treated as inactive and
// its slot is silently reclaimed by the next different device that asks -
// covers "got a new phone" / "reinstalled Windows" without a support ticket,
// while still blocking two devices actively sharing one key at the same time
// (an active device refreshes its own last_seen well inside this window).
const STALE_SLOT_SECONDS = 90 * 24 * 3600;

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const key = url.searchParams.get("key");
  if (!key) return jsonResponse({ valid: false, error: "missing key" }, 400);

  const row = await env.DB.prepare(
    `SELECT tier, status, current_period_end FROM licenses WHERE license_key = ?`,
  )
    .bind(key)
    .first();

  if (!row) return jsonResponse({ valid: false });

  const now = Math.floor(Date.now() / 1000);
  const expired =
    row.status !== "active" ||
    (row.tier !== "lifetime" && row.current_period_end !== null && row.current_period_end < now);
  const valid = !expired;

  // platform/device_id are opt-in: older clients (or LicenseManager
  // constructed without a platform, e.g. Termux/desktop-CLI) just omit them,
  // and device_allowed then defaults true so nothing changes for them.
  const platform = url.searchParams.get("platform");
  const deviceId = url.searchParams.get("device_id");
  let deviceAllowed = true;
  if (valid && platform && deviceId) {
    const appVersion = url.searchParams.get("app_version") || null;
    deviceAllowed = await checkDeviceSlot(env, key, platform, deviceId, appVersion, now);
  }

  return jsonResponse({
    valid,
    tier: row.tier,
    status: expired ? "expired" : row.status,
    device_allowed: deviceAllowed,
  });
}

// One active device slot per (license, platform). Returns whether `deviceId`
// holds (or has just been granted) that slot.
async function checkDeviceSlot(env, key, platform, deviceId, appVersion, now) {
  const keyHash = await sha256Hex(key);
  const deviceHash = await sha256Hex(deviceId);

  const existing = await env.DB.prepare(
    `SELECT id FROM license_activations
     WHERE license_key_hash = ? AND platform = ? AND device_id_hash = ? AND revoked_at IS NULL`,
  )
    .bind(keyHash, platform, deviceHash)
    .first();

  if (existing) {
    await env.DB.prepare(`UPDATE license_activations SET last_seen = ?, app_version = ? WHERE id = ?`)
      .bind(now, appVersion, existing.id)
      .run();
    return true;
  }

  const other = await env.DB.prepare(
    `SELECT id, last_seen FROM license_activations
     WHERE license_key_hash = ? AND platform = ? AND revoked_at IS NULL`,
  )
    .bind(keyHash, platform)
    .first();

  if (other) {
    if (now - other.last_seen < STALE_SLOT_SECONDS) {
      return false;
    }
    await env.DB.prepare(`UPDATE license_activations SET revoked_at = ? WHERE id = ?`).bind(now, other.id).run();
  }

  await env.DB.prepare(
    `INSERT INTO license_activations
      (license_key_hash, platform, device_id_hash, first_seen, last_seen, app_version)
     VALUES (?, ?, ?, ?, ?, ?)`,
  )
    .bind(keyHash, platform, deviceHash, now, now, appVersion)
    .run();
  return true;
}
