import test from "node:test";
import assert from "node:assert/strict";
import { makeEnv } from "./helpers/fake-d1.mjs";
import { markPlayEntitlementDelivered, requestPlayRefund } from "../functions/_play_refunds.js";
import { verifyAndApplyPlayPurchase } from "../functions/_google_play.js";

const TOKEN_KEY = Buffer.alloc(32, 9).toString("base64");
const DEVICE = "stable-install-device-0001";

function purchaseResponse({ orderId, ageHours = 1, token = "valid-purchase-token-0001" } = {}) {
  return {
    token,
    body: {
      purchaseStateContext: { purchaseState: "PURCHASED" },
      productLineItem: [{ productId: "pro", latestSuccessfulOrderId: orderId || `GPA.${token.slice(-8)}` }],
      purchaseCompletionTime: new Date(Date.now() - ageHours * 3600_000).toISOString(),
      acknowledgementState: "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
    },
  };
}

function refundEnv(purchases, enabled = true) {
  const byToken = new Map(purchases.map((purchase) => [purchase.token, purchase.body]));
  const refundCalls = [];
  const env = makeEnv({
    PLAY_PACKAGE_NAME: "de.classydl.app",
    PLAY_PRODUCT_ID: "pro",
    PLAY_TOKEN_ENCRYPTION_KEY: TOKEN_KEY,
    PLAY_ACCESS_TOKEN_FOR_TESTS: "test-token",
    PLAY_AUTOMATED_REFUNDS_ENABLED: enabled ? "true" : "false",
    PLAY_FETCH: async (url) => {
      if (url.includes("/purchases/productsv2/tokens/")) {
        const token = decodeURIComponent(url.split("/tokens/")[1]);
        const body = byToken.get(token);
        return body ? new Response(JSON.stringify(body), { status: 200 }) : new Response("", { status: 404 });
      }
      if (url.includes(":refund")) {
        refundCalls.push(url);
        return new Response(null, { status: 204 });
      }
      if (url.includes(":acknowledge")) return new Response("", { status: 200 });
      return new Response("", { status: 500 });
    },
  });
  return { env, refundCalls };
}

test("a token not verified by Google can never create a refund", async () => {
  const { env, refundCalls } = refundEnv([]);
  await assert.rejects(
    requestPlayRefund(env, {
      purchaseToken: "forged-purchase-token-0001",
      deviceId: DEVICE,
      reason: "technical_failure",
    }),
  );
  assert.equal(refundCalls.length, 0);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS count FROM play_refund_requests").first()).count, 0);
});

test("a verified purchase within 48 hours is refunded and revoked exactly once", async () => {
  const purchase = purchaseResponse({ orderId: "GPA.48-HOUR", ageHours: 24 });
  const { env, refundCalls } = refundEnv([purchase]);
  const request = { purchaseToken: purchase.token, deviceId: DEVICE, reason: "accidental_purchase" };
  const first = await requestPlayRefund(env, request);
  const second = await requestPlayRefund(env, request);
  assert.equal(first.status, "refunded");
  assert.equal(first.revoked, true);
  assert.equal(second.request_id, first.request_id);
  assert.equal(refundCalls.length, 1);
  const mapping = await env.DB.prepare("SELECT purchase_state FROM play_purchases").first();
  assert.equal(mapping.purchase_state, "revoked");
});

test("days 3 to 14 auto-refund only objective technical non-delivery", async () => {
  const missing = purchaseResponse({ token: "valid-purchase-token-0002", orderId: "GPA.MISSING", ageHours: 5 * 24 });
  const delivered = purchaseResponse({ token: "valid-purchase-token-0003", orderId: "GPA.DELIVERED", ageHours: 5 * 24 });
  const { env, refundCalls } = refundEnv([missing, delivered]);

  const missingResult = await requestPlayRefund(env, {
    purchaseToken: missing.token, deviceId: "stable-install-device-0002", reason: "technical_failure",
  });
  assert.equal(missingResult.status, "refunded");

  // Establish and confirm delivery before asking for the second refund.
  await requestPlayRefund(env, {
    purchaseToken: delivered.token, deviceId: "stable-install-device-0003", reason: "other",
  });
  await markPlayEntitlementDelivered(env, {
    purchaseToken: delivered.token, deviceId: "stable-install-device-0003",
  });
  // The first request is idempotent and stays in manual review; delivery can
  // never upgrade an existing request into an automatic refund.
  const deliveredResult = await requestPlayRefund(env, {
    purchaseToken: delivered.token, deviceId: "stable-install-device-0003", reason: "technical_failure",
  });
  assert.equal(deliveredResult.status, "manual_review");
  assert.equal(refundCalls.length, 1);
});

test("automation disabled and repeat-refund devices always go to manual review", async () => {
  const first = purchaseResponse({ token: "valid-purchase-token-0004", orderId: "GPA.FIRST", ageHours: 1 });
  const second = purchaseResponse({ token: "valid-purchase-token-0005", orderId: "GPA.SECOND", ageHours: 1 });
  const disabled = purchaseResponse({ token: "valid-purchase-token-0006", orderId: "GPA.DISABLED", ageHours: 1 });
  const active = refundEnv([first, second]);
  assert.equal((await requestPlayRefund(active.env, {
    purchaseToken: first.token, deviceId: DEVICE, reason: "other",
  })).status, "refunded");
  const repeated = await requestPlayRefund(active.env, {
    purchaseToken: second.token, deviceId: DEVICE, reason: "technical_failure",
  });
  assert.equal(repeated.status, "manual_review");
  assert.equal(repeated.policy_reason, "repeat_refund_manual_review");
  assert.equal(active.refundCalls.length, 1);

  const off = refundEnv([disabled], false);
  const disabledResult = await requestPlayRefund(off.env, {
    purchaseToken: disabled.token, deviceId: "stable-install-device-0006", reason: "technical_failure",
  });
  assert.equal(disabledResult.status, "manual_review");
  assert.equal(disabledResult.policy_reason, "automation_disabled");
  assert.equal(off.refundCalls.length, 0);
});

test("a different installation cannot automatically refund a delivered purchase", async () => {
  const purchase = purchaseResponse({ token: "valid-purchase-token-0007", orderId: "GPA.DEVICE", ageHours: 1 });
  const { env, refundCalls } = refundEnv([purchase]);
  await verifyAndApplyPlayPurchase(env, purchase.token);
  await markPlayEntitlementDelivered(env, {
    purchaseToken: purchase.token,
    deviceId: "original-install-device-0007",
  });
  const result = await requestPlayRefund(env, {
    purchaseToken: purchase.token,
    deviceId: "different-install-device-0007",
    reason: "technical_failure",
  });
  assert.equal(result.status, "manual_review");
  assert.equal(result.policy_reason, "device_mismatch_manual_review");
  assert.equal(refundCalls.length, 0);
});
