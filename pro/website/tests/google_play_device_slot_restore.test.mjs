import assert from "node:assert/strict";
import test from "node:test";

import { makeEnv } from "./helpers/fake-d1.mjs";
import { validateLicense } from "../functions/_license_validation.js";
import { onRequestPost as verifyPurchase } from "../functions/api/play/purchases/verify.js";

const TOKEN_KEY = Buffer.alloc(32, 11).toString("base64");

function purchase() {
  return {
    purchaseStateContext: { purchaseState: "PURCHASED" },
    productLineItem: [{ productId: "pro", latestSuccessfulOrderId: "GPA.REINSTALL-TEST" }],
    acknowledgementState: "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
  };
}

function envForPlay() {
  return makeEnv({
    PLAY_PACKAGE_NAME: "de.classydl.app",
    PLAY_PRODUCT_ID: "pro",
    PLAY_TOKEN_ENCRYPTION_KEY: TOKEN_KEY,
    PLAY_ACCESS_TOKEN_FOR_TESTS: "test-access-token",
    PLAY_FETCH: async () => Response.json(purchase()),
  });
}

async function verify(env, deviceId) {
  const response = await verifyPurchase({
    env,
    request: new Request("https://example.test/api/play/purchases/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        purchase_token: "stable-reinstall-purchase-token",
        package_name: "de.classydl.app",
        product_id: "pro",
        device_id: deviceId,
        app_version: "1.0.4.1",
      }),
    }),
  });
  assert.equal(response.status, 200);
  return response.json();
}

test("verified Play restore transfers the single Android slot", async () => {
  const env = envForPlay();
  const firstDevice = "android-stable-device-0001";
  const secondDevice = "android-stable-device-0002";

  const first = await verify(env, firstDevice);
  assert.equal(first.entitled, true);
  assert.ok(first.license_key);

  const firstValidation = await validateLicense(env, {
    key: first.license_key,
    platform: "android",
    deviceId: firstDevice,
    appVersion: "1.0.4.1",
  });
  assert.equal(firstValidation.device_allowed, true);

  // Simulates reinstall/device recovery: Google verifies the same owned
  // purchase again, which is strong enough proof to move the one Android slot.
  const restored = await verify(env, secondDevice);
  assert.equal(restored.license_key, first.license_key);

  const restoredValidation = await validateLicense(env, {
    key: first.license_key,
    platform: "android",
    deviceId: secondDevice,
    appVersion: "1.0.4.1",
  });
  assert.equal(restoredValidation.device_allowed, true);

  const oldDeviceAfterTransfer = await validateLicense(env, {
    key: first.license_key,
    platform: "android",
    deviceId: firstDevice,
    appVersion: "1.0.4.1",
  });
  assert.equal(oldDeviceAfterTransfer.device_allowed, false);
});

test("plain license validation cannot evict an active Android slot", async () => {
  const env = envForPlay();
  const owner = "android-stable-device-0010";
  const copiedKeyDevice = "android-stable-device-0099";

  const purchaseResult = await verify(env, owner);
  const attempt = await validateLicense(env, {
    key: purchaseResult.license_key,
    platform: "android",
    deviceId: copiedKeyDevice,
    appVersion: "1.0.4.1",
  });

  assert.equal(attempt.valid, true);
  assert.equal(attempt.device_allowed, false);
});
