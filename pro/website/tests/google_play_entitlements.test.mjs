import assert from "node:assert/strict";
import test from "node:test";
import { makeEnv } from "./helpers/fake-d1.mjs";
import {
  decryptPurchaseToken,
  reconcilePlayPurchases,
  revokePlayPurchaseByToken,
  verifyAndApplyPlayPurchase,
  verifyGoogleOidcJwt,
} from "../functions/_google_play.js";
import { validateLicense } from "../functions/_license_validation.js";
import { onRequestPost as postValidate } from "../functions/api/license/validate.js";
import { onRequestGet as listGrants, onRequestPost as manageGrants } from "../functions/api/admin/tester-grants.js";
import { createTesterGrant } from "../functions/_tester_grants.js";

const TOKEN_KEY = Buffer.alloc(32, 7).toString("base64");

function playEnv(purchaseFactory) {
  const calls = [];
  const env = makeEnv({
    PLAY_PACKAGE_NAME: "de.classydl.app",
    PLAY_PRODUCT_ID: "pro",
    PLAY_TOKEN_ENCRYPTION_KEY: TOKEN_KEY,
    PLAY_ACCESS_TOKEN_FOR_TESTS: "test-access-token",
    PLAY_FETCH: async (url, options = {}) => {
      calls.push({ url: String(url), options });
      if (String(url).endsWith(":acknowledge")) return new Response(null, { status: 200 });
      return Response.json(purchaseFactory());
    },
  });
  return { env, calls };
}

function purchase(state = "PURCHASED", productId = "pro") {
  return {
    purchaseStateContext: { purchaseState: state },
    productLineItem: [{ productId, latestSuccessfulOrderId: "GPA.1234-5678" }],
    acknowledgementState: "ACKNOWLEDGEMENT_STATE_PENDING",
  };
}

test("PURCHASED grants one stable license, encrypts the token and acknowledges", async () => {
  const { env, calls } = playEnv(() => purchase());
  const first = await verifyAndApplyPlayPurchase(env, "secret-purchase-token");
  const second = await verifyAndApplyPlayPurchase(env, "secret-purchase-token");
  assert.equal(first.entitled, true);
  assert.equal(second.licenseKey, first.licenseKey);
  assert.match(first.licenseKey, /^DLT-[A-F0-9]{8}-[A-F0-9]{8}-[A-F0-9]{8}$/);
  const rows = await env.DB.prepare("SELECT * FROM play_purchases").all();
  assert.equal(rows.results.length, 1);
  assert.equal(rows.results[0].purchase_state, "purchased");
  assert.notEqual(rows.results[0].purchase_token_ciphertext, "secret-purchase-token");
  assert.equal(
    await decryptPurchaseToken(env, rows.results[0].purchase_token_ciphertext, rows.results[0].purchase_token_iv),
    "secret-purchase-token",
  );
  assert.equal(calls.filter((call) => call.url.endsWith(":acknowledge")).length, 1);
});

test("a transient acknowledgement failure is retried without minting another license", async () => {
  let acknowledgementAttempts = 0;
  const env = makeEnv({
    PLAY_PACKAGE_NAME: "de.classydl.app",
    PLAY_PRODUCT_ID: "pro",
    PLAY_TOKEN_ENCRYPTION_KEY: TOKEN_KEY,
    PLAY_ACCESS_TOKEN_FOR_TESTS: "test-access-token",
    PLAY_FETCH: async (url) => {
      if (String(url).endsWith(":acknowledge")) {
        acknowledgementAttempts++;
        return new Response(null, { status: acknowledgementAttempts === 1 ? 503 : 200 });
      }
      return Response.json(purchase());
    },
  });

  const first = await verifyAndApplyPlayPurchase(env, "ack-retry-purchase-token");
  const second = await verifyAndApplyPlayPurchase(env, "ack-retry-purchase-token");

  assert.equal(first.entitled, true);
  assert.equal(first.acknowledged, false);
  assert.equal(second.acknowledged, true);
  assert.equal(second.licenseKey, first.licenseKey);
  assert.equal(acknowledgementAttempts, 2);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS count FROM licenses").first()).count, 1);
});

test("PENDING is recorded but never grants Pro", async () => {
  const { env } = playEnv(() => purchase("PENDING"));
  const result = await verifyAndApplyPlayPurchase(env, "pending-purchase-token");
  assert.deepEqual(result, { entitled: false, state: "pending" });
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS count FROM licenses").first()).count, 0);
});

test("unknown Google purchase state neither grants nor revokes", async () => {
  let state = "PURCHASED";
  const { env } = playEnv(() => purchase(state));
  const granted = await verifyAndApplyPlayPurchase(env, "unknown-state-purchase-token");
  state = "PURCHASE_STATE_UNSPECIFIED";

  await assert.rejects(
    () => verifyAndApplyPlayPurchase(env, "unknown-state-purchase-token"),
    /unsupported Google Play purchase state/,
  );
  assert.equal((await validateLicense(env, { key: granted.licenseKey })).valid, true);
});

test("app-facing verification cannot revoke an established entitlement", async () => {
  let state = "PURCHASED";
  const { env } = playEnv(() => purchase(state));
  const granted = await verifyAndApplyPlayPurchase(env, "client-recheck-purchase-token");
  state = "CANCELLED";

  const recheck = await verifyAndApplyPlayPurchase(env, "client-recheck-purchase-token");
  assert.equal(recheck.entitled, false);
  assert.equal(recheck.state, "revoke_pending");
  assert.equal((await validateLicense(env, { key: granted.licenseKey })).valid, true);

  const reconciled = await reconcilePlayPurchases(env, 100);
  assert.equal(reconciled.revoked, 1);
  assert.equal((await validateLicense(env, { key: granted.licenseKey })).valid, false);
});

test("wrong verified product and caller-supplied package fail closed", async () => {
  const { env } = playEnv(() => purchase("PURCHASED", "other_product"));
  await assert.rejects(() => verifyAndApplyPlayPurchase(env, "wrong-product-token"), /unexpected product/);
  await assert.rejects(
    () => verifyAndApplyPlayPurchase(env, "wrong-package-token", { packageName: "evil.example" }),
    /unexpected package or product/,
  );
});

test("refund/revocation disables the same cross-platform license", async () => {
  const { env } = playEnv(() => purchase());
  const granted = await verifyAndApplyPlayPurchase(env, "refunded-purchase-token");
  assert.equal((await validateLicense(env, { key: granted.licenseKey })).valid, true);
  assert.equal(await revokePlayPurchaseByToken(env, "refunded-purchase-token"), true);
  const validation = await validateLicense(env, { key: granted.licenseKey });
  assert.equal(validation.valid, false);
  assert.equal(validation.provider, "google_play");
});

test("repeat revocation does not extend the original refund timestamp", async () => {
  const { env } = playEnv(() => purchase());
  await verifyAndApplyPlayPurchase(env, "stable-revocation-token");
  await revokePlayPurchaseByToken(env, "stable-revocation-token");
  await env.DB.prepare("UPDATE play_purchases SET revoked_at = 123").run();
  await revokePlayPurchaseByToken(env, "stable-revocation-token");
  const second = await env.DB.prepare(
    "SELECT revoked_at FROM play_purchases WHERE token_hash IS NOT NULL",
  ).first();
  assert.equal(second.revoked_at, 123);
});

test("POST license validation avoids query strings and returns 72-hour Play grace", async () => {
  const { env } = playEnv(() => purchase());
  const granted = await verifyAndApplyPlayPurchase(env, "validation-purchase-token");
  const request = new Request("https://example.test/api/license/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: granted.licenseKey, platform: "windows", device_id: "device-a" }),
  });
  const response = await postValidate({ request, env });
  const body = await response.json();
  assert.equal(body.valid, true);
  assert.equal(body.provider, "google_play");
  assert.equal(body.offline_grace_until - body.verified_at, 72 * 3600);
});

test("owner and expiring tester grants validate without storing raw keys", async () => {
  const { env } = playEnv(() => purchase());
  const owner = await createTesterGrant(env, { label: "Owner", grantType: "owner", expiresAt: null });
  const tester = await createTesterGrant(env, {
    label: "Beta Alice",
    grantType: "tester",
    expiresAt: Math.floor(Date.now() / 1000) + 3600,
  });
  assert.equal((await validateLicense(env, { key: owner.key })).tier, "owner");
  const valid = await validateLicense(env, { key: tester.key, platform: "windows", deviceId: "tester-a" });
  assert.equal(valid.valid, true);
  assert.equal(valid.provider, "manual");
  assert.equal(valid.label, "Beta Alice");
  const raw = await env.DB.prepare("SELECT key_hash FROM tester_grants WHERE id = ?").bind(tester.id).first();
  assert.notEqual(raw.key_hash, tester.key);
});

test("tester grant admin API creates, lists and revokes bearer keys", async () => {
  const { env } = playEnv(() => purchase());
  env.TESTER_GRANTS_ADMIN_TOKEN = "admin-secret";
  const unauthorized = await manageGrants({
    request: new Request("https://example.test/api/admin/tester-grants", { method: "POST", body: "{}" }),
    env,
  });
  assert.equal(unauthorized.status, 401);
  const created = await manageGrants({
    request: new Request("https://example.test/api/admin/tester-grants", {
      method: "POST",
      headers: { Authorization: "Bearer admin-secret", "Content-Type": "application/json" },
      body: JSON.stringify({ label: "Beta Bob", grant_type: "tester", expires_in_days: 7 }),
    }),
    env,
  });
  assert.equal(created.status, 201);
  const createdBody = await created.json();
  assert.match(createdBody.key, /^DT-TEST-/);
  const listed = await listGrants({
    request: new Request("https://example.test/api/admin/tester-grants", {
      headers: { Authorization: "Bearer admin-secret" },
    }),
    env,
  });
  const listedBody = await listed.json();
  assert.equal(listedBody.grants.length, 1);
  assert.equal("key" in listedBody.grants[0], false);
  const revoked = await manageGrants({
    request: new Request("https://example.test/api/admin/tester-grants", {
      method: "POST",
      headers: { Authorization: "Bearer admin-secret", "Content-Type": "application/json" },
      body: JSON.stringify({ action: "revoke", id: createdBody.id }),
    }),
    env,
  });
  assert.equal(revoked.status, 200);
  assert.equal((await validateLicense(env, { key: createdBody.key })).valid, false);
});

test("daily reconciliation decrypts tokens and applies a later cancellation", async () => {
  let state = "PURCHASED";
  const { env } = playEnv(() => purchase(state));
  const granted = await verifyAndApplyPlayPurchase(env, "reconciliation-purchase-token");
  state = "CANCELLED";
  const result = await reconcilePlayPurchases(env, 100);
  assert.equal(result.checked, 1);
  assert.equal(result.revoked, 1);
  assert.equal((await validateLicense(env, { key: granted.licenseKey })).valid, false);
});

test("daily reconciliation revokes a previously valid token that Google now returns as gone", async () => {
  const { env } = playEnv(() => purchase());
  const granted = await verifyAndApplyPlayPurchase(env, "gone-purchase-token");
  env.PLAY_FETCH = async (url) => {
    if (String(url).endsWith(":acknowledge")) return new Response(null, { status: 200 });
    return new Response(null, { status: 404 });
  };
  const result = await reconcilePlayPurchases(env, 100);
  assert.equal(result.revoked, 1);
  assert.equal(result.failed, 0);
  assert.equal((await validateLicense(env, { key: granted.licenseKey })).valid, false);
});

function base64Url(value) {
  return Buffer.from(value).toString("base64url");
}

test("RTDN Google OIDC verifier validates signature, audience and service-account email", async () => {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  Object.assign(jwk, { kid: "test-key", alg: "RS256", use: "sig" });
  const now = Math.floor(Date.now() / 1000);
  const header = base64Url(JSON.stringify({ alg: "RS256", typ: "JWT", kid: "test-key" }));
  const payload = base64Url(JSON.stringify({
    iss: "https://accounts.google.com",
    aud: "https://example.test/api/play/rtdn",
    email: "pubsub@example.iam.gserviceaccount.com",
    email_verified: true,
    iat: now - 10,
    exp: now + 600,
  }));
  const input = `${header}.${payload}`;
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", pair.privateKey, Buffer.from(input));
  const jwt = `${input}.${Buffer.from(signature).toString("base64url")}`;
  const env = {
    PLAY_RTDN_AUDIENCE: "https://example.test/api/play/rtdn",
    PLAY_RTDN_SERVICE_ACCOUNT_EMAIL: "pubsub@example.iam.gserviceaccount.com",
  };
  const fetchJwks = async () => Response.json({ keys: [jwk] });
  const claims = await verifyGoogleOidcJwt(jwt, env, fetchJwks);
  assert.equal(claims.email, env.PLAY_RTDN_SERVICE_ACCOUNT_EMAIL);
  assert.equal(await verifyGoogleOidcJwt(jwt, { ...env, PLAY_RTDN_AUDIENCE: "wrong" }, fetchJwks), null);
});
