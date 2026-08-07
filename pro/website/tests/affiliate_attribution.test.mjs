import test from "node:test";
import assert from "node:assert/strict";
import { makeEnv } from "./helpers/fake-d1.mjs";
import { createReferralClaim, recordReferralClick } from "../functions/_affiliate.js";
import { attributeVerifiedPurchase, releaseMatureCommissions, voidAffiliatePurchase } from "../functions/_affiliate_commissions.js";
import { onRequestGet as referralGet } from "../functions/r/[affiliateCode].js";
import { onRequestPost as attributionPost } from "../functions/api/affiliate/attributions.js";
import { onRequestPost as adminPost } from "../functions/api/admin/affiliates.js";
import { onRequestPost as rtdnPost } from "../functions/api/play/rtdn.js";
import { onRequestGet as dashboardGet } from "../functions/api/admin/affiliates/dashboard.js";
import { onRequestGet as affiliateDashboardGet } from "../functions/api/affiliate/dashboard.js";
import { cleanupAffiliateRetention } from "../functions/_affiliate_retention.js";

const FLAGS = {
  AFFILIATE_ENABLED: "true",
  AFFILIATE_PRODUCTION_APPROVED: "true",
  AFFILIATE_REDIRECT_ENABLED: "true",
  AFFILIATE_ATTRIBUTION_ENABLED: "true",
  AFFILIATE_COMMISSION_ENABLED: "true",
  AFFILIATE_ADMIN_ENABLED: "true",
  AFFILIATE_ADMIN_TOKEN: "admin-secret",
  AFFILIATE_SIGNING_SECRET: "signing-secret",
  AFFILIATE_INSTALL_HASH_SALT: "install-salt",
  AFFILIATE_NOW_SECONDS: "1730000000",
  PLAY_STORE_URL: "https://play.google.com/store/apps/details?id=de.classydl.app",
};

function base64Url(value) {
  return Buffer.from(value).toString("base64url");
}

async function rtdnAuth() {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  Object.assign(jwk, { kid: "affiliate-test", alg: "RS256", use: "sig" });
  const now = Math.floor(Date.now() / 1000);
  const header = base64Url(JSON.stringify({ alg: "RS256", typ: "JWT", kid: "affiliate-test" }));
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
  return {
    jwt: `${input}.${Buffer.from(signature).toString("base64url")}`,
    fetchJwks: async () => Response.json({ keys: [jwk] }),
  };
}

async function seedAffiliate(env, commissionValue = 250) {
  await env.DB.prepare(
    `INSERT INTO affiliates (id, code, display_name, status, commission_type, commission_value_minor,
      commission_rate_bps, created_at, approved_at, disabled_at, updated_at)
     VALUES ('aff-1', 'creator', 'Creator', 'active', 'fixed', ?, 0, ?, ?, NULL, ?)`,
  ).bind(commissionValue, 1730000000, 1730000000, 1730000000).run();
}

test("feature flags keep referral route closed", async () => {
  const env = makeEnv({ ...FLAGS, AFFILIATE_ENABLED: "false" });
  const response = await referralGet({ params: { affiliateCode: "creator" }, env });
  assert.equal(response.status, 404);
});

test("runtime owner gate keeps affiliate disabled without explicit approval", async () => {
  const env = makeEnv({ ...FLAGS, AFFILIATE_PRODUCTION_APPROVED: "false" });
  const response = await referralGet({ params: { affiliateCode: "creator" }, env });
  assert.equal(response.status, 404);
});

test("redirect rate limit is per affiliate and produces only redacted audit data", async () => {
  const env = makeEnv({ ...FLAGS, AFFILIATE_CLICK_RATE_LIMIT_PER_HOUR: "1" });
  await seedAffiliate(env);
  assert.equal((await referralGet({ params: { affiliateCode: "creator" }, env })).status, 302);
  const limited = await referralGet({ params: { affiliateCode: "creator" }, env });
  assert.equal(limited.status, 429);
  const audit = await env.DB.prepare("SELECT event_type, reason FROM affiliate_audit_events WHERE event_type = 'affiliate.click.rate_limited' LIMIT 1").first();
  assert.equal(audit.event_type, "affiliate.click.rate_limited");
  assert.equal(audit.reason, "hourly redirect limit");
});

test("referral redirect is Play-fixed and attribution is immutable/idempotent", async () => {
  const env = makeEnv(FLAGS);
  await seedAffiliate(env);
  const redirect = await referralGet({ params: { affiliateCode: "creator" }, env });
  assert.equal(redirect.status, 302);
  const location = new URL(redirect.headers.get("location"));
  assert.equal(location.origin, "https://play.google.com");
  assert.equal(location.searchParams.get("id"), "de.classydl.app");
  const referrer = location.searchParams.get("referrer");
  const body = {
    install_id: "install-device-000001",
    referrer,
    referrer_click_timestamp_seconds: 1730000000,
    app_install_timestamp_seconds: 1730000010,
  };
  const first = await attributionPost({
    request: new Request("https://downloadthat.app/api/affiliate/attributions", { method: "POST", body: JSON.stringify(body) }),
    env,
  });
  assert.equal(first.status, 200);
  const second = await attributionPost({
    request: new Request("https://downloadthat.app/api/affiliate/attributions", { method: "POST", body: JSON.stringify(body) }),
    env,
  });
  assert.equal(second.status, 200);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS count FROM install_attributions").first()).count, 1);
  const other = await attributionPost({
    request: new Request("https://downloadthat.app/api/affiliate/attributions", { method: "POST", body: JSON.stringify({ ...body, install_id: "install-device-000002" }) }),
    env,
  });
  assert.equal(other.status, 409);
});

test("admin lifecycle and fixed commission release/void are idempotent", async () => {
  const env = makeEnv(FLAGS);
  const created = await adminPost({
    request: new Request("https://downloadthat.app/api/admin/affiliates", {
      method: "POST", headers: { Authorization: "Bearer admin-secret" },
      body: JSON.stringify({ code: "newcreator", display_name: "New Creator", status: "active", commission_value_minor: 100 }),
    }), env,
  });
  assert.equal(created.status, 201);
  const status = await adminPost({
    request: new Request("https://downloadthat.app/api/admin/affiliates", {
      method: "POST", headers: { Authorization: "Bearer admin-secret" },
      body: JSON.stringify({ action: "set_status", id: JSON.parse(await created.text()).id, status: "disabled" }),
    }), env,
  });
  assert.equal(status.status, 200);
  await seedAffiliate(env, 250);
  const click = await recordReferralClick(env, "creator");
  const referrer = await createReferralClaim(env, click.clickId, click.expiresAt);
  await attributionPost({
    request: new Request("https://downloadthat.app/api/affiliate/attributions", { method: "POST", body: JSON.stringify({ install_id: "install-device-000003", referrer }) }),
    env,
  });
  const token = "purchase-token-1";
  const { sha256Hex } = await import("../functions/_lib.js");
  const tokenHash = await sha256Hex(token);
  const deviceHash = await sha256Hex("install-device-000003");
  await env.DB.prepare(
    `INSERT INTO play_purchases (token_hash, purchase_token_ciphertext, purchase_token_iv, order_id, package_name,
      product_id, purchase_state, verified_at, purchase_completed_at, purchase_device_id_hash, created_at, updated_at)
     VALUES (?, 'cipher', 'iv', 'order-1', 'de.classydl.app', 'pro', 'purchased', ?, ?, ?, ?, ?)`,
  ).bind(tokenHash, 1730000000, 1730000000, deviceHash, 1730000000, 1730000000).run();
  const linked = await attributeVerifiedPurchase(env, { deviceId: "install-device-000003", purchaseToken: token });
  assert.equal(linked.linked, true);
  assert.equal((await env.DB.prepare("SELECT commission_amount_minor AS amount FROM affiliate_commissions").first()).amount, 250);
  env.AFFILIATE_NOW_SECONDS = "1732592001";
  assert.equal((await releaseMatureCommissions(env)).released, 1);
  assert.equal(await voidAffiliatePurchase(env, { purchaseTokenHash: tokenHash, reason: "refund" }), true);
  assert.equal((await env.DB.prepare("SELECT status FROM affiliate_commissions").first()).status, "voided");
  assert.equal(await voidAffiliatePurchase(env, { purchaseTokenHash: tokenHash, reason: "refund" }), true);
});

test("dashboard is separately gated, aggregate-only, and retention defaults to dry-run", async () => {
  const env = makeEnv({ ...FLAGS, AFFILIATE_DASHBOARD_ENABLED: "true" });
  await seedAffiliate(env);
  const dashboard = await dashboardGet({
    request: new Request("https://downloadthat.app/api/admin/affiliates/dashboard", { headers: { Authorization: "Bearer admin-secret" } }),
    env,
  });
  assert.equal(dashboard.status, 200);
  const dashboardBody = await dashboard.json();
  assert.equal(dashboardBody.privacy.raw_tokens, false);
  assert.equal("purchase_token" in dashboardBody, false);
  assert.equal("buyer" in dashboardBody, false);
  const dryRun = await cleanupAffiliateRetention(env, { now: 1730000000 });
  assert.equal(dryRun.dry_run, true);
  assert.equal(dryRun.deleted_clicks, 0);
  env.AFFILIATE_NOW_SECONDS = "1730000000";
  const oldClick = await recordReferralClick(env, "creator");
  const oldClaim = await createReferralClaim(env, oldClick.clickId, oldClick.expiresAt);
  await attributionPost({
    request: new Request("https://downloadthat.app/api/affiliate/attributions", { method: "POST", body: JSON.stringify({ install_id: "old-install-device-0001", referrer: oldClaim }) }),
    env,
  });
  const cleaned = await cleanupAffiliateRetention(env, { now: 1730000000 + 200 * 24 * 60 * 60, dryRun: false });
  assert.equal(cleaned.deleted_attributions, 1);
  assert.equal(cleaned.deleted_clicks, 1);
});

test("affiliate dashboard access is scoped to its own hashed bearer token", async () => {
  const env = makeEnv({ ...FLAGS, AFFILIATE_DASHBOARD_ENABLED: "true" });
  await seedAffiliate(env);
  const created = await adminPost({
    request: new Request("https://downloadthat.app/api/admin/affiliates", {
      method: "POST", headers: { Authorization: "Bearer admin-secret" },
      body: JSON.stringify({ action: "create_access_token", affiliate_id: "aff-1", label: "pilot" }),
    }), env,
  });
  assert.equal(created.status, 201);
  const tokenBody = await created.json();
  assert.match(tokenBody.token, /^afp_/);
  const dashboard = await affiliateDashboardGet({
    request: new Request("https://downloadthat.app/api/affiliate/dashboard", { headers: { Authorization: `Bearer ${tokenBody.token}` } }),
    env,
  });
  assert.equal(dashboard.status, 200);
  const body = await dashboard.json();
  assert.equal(body.affiliate.code, "creator");
  assert.equal(body.totals.clicks, 0);
  assert.equal(body.privacy.order_ids, false);
  assert.equal("token_hash" in body, false);
  assert.equal((await affiliateDashboardGet({ request: new Request("https://downloadthat.app/api/affiliate/dashboard", { headers: { Authorization: "Bearer wrong" } }), env })).status, 401);
  const revoked = await adminPost({
    request: new Request("https://downloadthat.app/api/admin/affiliates", {
      method: "POST", headers: { Authorization: "Bearer admin-secret" },
      body: JSON.stringify({ action: "revoke_access_token", id: tokenBody.id }),
    }), env,
  });
  assert.equal(revoked.status, 200);
  assert.equal((await affiliateDashboardGet({ request: new Request("https://downloadthat.app/api/affiliate/dashboard", { headers: { Authorization: `Bearer ${tokenBody.token}` } }), env })).status, 401);
});

test("RTDN message ID is durably deduplicated before affiliate side effects", async () => {
  const auth = await rtdnAuth();
  const env = makeEnv({ ...FLAGS,
    PLAY_RTDN_AUDIENCE: "https://example.test/api/play/rtdn",
    PLAY_RTDN_SERVICE_ACCOUNT_EMAIL: "pubsub@example.iam.gserviceaccount.com",
    OIDC_FETCH: auth.fetchJwks,
  });
  const body = { message: { messageId: "message-1", data: Buffer.from(JSON.stringify({ packageName: "de.classydl.app", testNotification: {} })).toString("base64") } };
  const first = await rtdnPost({ request: new Request("https://example.test/api/play/rtdn", { method: "POST", headers: { Authorization: `Bearer ${auth.jwt}` }, body: JSON.stringify(body) }), env });
  const second = await rtdnPost({ request: new Request("https://example.test/api/play/rtdn", { method: "POST", headers: { Authorization: `Bearer ${auth.jwt}` }, body: JSON.stringify(body) }), env });
  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
  assert.equal((await second.json()).duplicate, true);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS count FROM affiliate_event_inbox WHERE external_event_id = 'message-1'").first()).count, 1);
});
