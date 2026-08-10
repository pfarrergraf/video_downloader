import assert from "node:assert/strict";
import test from "node:test";
import { makeEnv } from "./helpers/fake-d1.mjs";
import { sha256Hex } from "../functions/_lib.js";
import {
  grantPlayPurchaseCooldownBypass,
  playPurchaseEligibility,
} from "../functions/_play_purchase_eligibility.js";

const DEVICE_ID = "release-test-device-0001";
const NOW = 2_000_000_000;
const DAY = 86_400;

async function addRefund(env, index, refundedAt) {
  const tokenHash = await sha256Hex(`purchase-token-${index}`);
  const deviceHash = await sha256Hex(DEVICE_ID);
  await env.DB.prepare(
    `INSERT INTO play_purchases
       (token_hash, purchase_token_ciphertext, purchase_token_iv, order_id, package_name,
        product_id, purchase_state, license_key, verified_at, acknowledged_at, revoked_at,
        purchase_completed_at, created_at, updated_at)
     VALUES (?, 'ciphertext', 'iv', ?, 'de.classydl.app', 'pro', 'revoked', NULL,
       ?, NULL, ?, ?, ?, ?)`,
  ).bind(tokenHash, `GPA.${index}`, refundedAt, refundedAt, refundedAt - 60, refundedAt, refundedAt).run();
  const id = `refund-${index}`;
  await env.DB.prepare(
    `INSERT INTO play_refund_requests
       (id, token_hash, order_id, device_id_hash, reason, status, policy_reason,
        requested_at, decided_at, refunded_at, updated_at, last_error)
     VALUES (?, ?, ?, ?, 'other', 'refunded', 'test', ?, ?, ?, ?, NULL)`,
  ).bind(id, tokenHash, `GPA.${index}`, deviceHash, refundedAt - 10, refundedAt, refundedAt, refundedAt).run();
  return id;
}

test("refund cooldowns escalate from one day to six months", async () => {
  for (const [count, days] of [[1, 1], [2, 7], [3, 30], [4, 180], [5, 180]]) {
    const env = makeEnv({ PLAY_NOW_SECONDS: String(NOW) });
    for (let index = 1; index <= count; index++) await addRefund(env, index, NOW - 60);
    const result = await playPurchaseEligibility(env, DEVICE_ID);
    assert.equal(result.eligible, false);
    assert.equal(result.refund_count, count);
    assert.equal(result.blocked_until, NOW - 60 + days * DAY);
  }
});

test("free purchase eligibility resumes after the cooldown", async () => {
  const env = makeEnv({ PLAY_NOW_SECONDS: String(NOW) });
  await addRefund(env, 1, NOW - DAY - 1);
  assert.equal((await playPurchaseEligibility(env, DEVICE_ID)).eligible, true);
});

test("admin test bypass is time-limited and keeps refund history", async () => {
  const env = makeEnv({ PLAY_NOW_SECONDS: String(NOW) });
  const requestId = await addRefund(env, 1, NOW - 60);
  const granted = await grantPlayPurchaseCooldownBypass(env, { refundRequestId: requestId, hours: 2 });
  assert.equal(granted.expires_at, NOW + 2 * 3600);
  const eligible = await playPurchaseEligibility(env, DEVICE_ID);
  assert.equal(eligible.eligible, true);
  assert.equal(eligible.refund_count, 1);
  assert.equal(eligible.test_bypass_until, granted.expires_at);

  env.PLAY_NOW_SECONDS = String(granted.expires_at + 1);
  assert.equal((await playPurchaseEligibility(env, DEVICE_ID)).eligible, false);
});
