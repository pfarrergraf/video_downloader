import test from "node:test";
import assert from "node:assert/strict";
import { makeEnv } from "./helpers/fake-d1.mjs";
import { createReferralClaim, recordReferralClick } from "../functions/_affiliate.js";
import { attributeVerifiedPurchase, releaseMatureCommissions, voidAffiliatePurchase } from "../functions/_affiliate_commissions.js";
import { onRequestGet as referralGet } from "../functions/r/[affiliateCode].js";
import { onRequestPost as attributionPost } from "../functions/api/affiliate/attributions.js";
import { onRequestPost as adminPost } from "../functions/api/admin/affiliates.js";

const FLAGS = {
  AFFILIATE_ENABLED: "true",
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
