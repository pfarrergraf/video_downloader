import test from "node:test";
import assert from "node:assert/strict";

import { makeEnv } from "./helpers/fake-d1.mjs";
import { sha256Hex } from "../functions/_lib.js";
import {
  eraseCustomerByEmail,
  exportCustomerByEmail,
  purgeExpiredClicks,
  purgeStaleActivations,
} from "../functions/_gdpr.js";

async function seedLicense(db, { key, email, tier = "lifetime" }) {
  const now = Math.floor(Date.now() / 1000);
  await db
    .prepare(
      `INSERT INTO licenses (license_key, tier, email, stripe_customer_id,
         stripe_checkout_session_id, status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, 'active', ?, ?)`,
    )
    .bind(key, tier, email, "cus_" + key, "cs_" + key, now, now)
    .run();
}

async function seedActivation(db, { key, platform = "android", revokedAt = null }) {
  const now = Math.floor(Date.now() / 1000);
  const keyHash = await sha256Hex(key);
  await db
    .prepare(
      `INSERT INTO license_activations (license_key_hash, platform, device_id_hash,
         first_seen, last_seen, app_version, revoked_at)
       VALUES (?, ?, ?, ?, ?, '1.0', ?)`,
    )
    .bind(keyHash, platform, "dev_" + key, now, now, revokedAt)
    .run();
}

test("eraseCustomerByEmail removes license rows and their activations", async () => {
  const env = makeEnv();
  await seedLicense(env.DB, { key: "DLT-A", email: "Buyer@Example.com" });
  await seedLicense(env.DB, { key: "DLT-B", email: "buyer@example.com" });
  await seedLicense(env.DB, { key: "DLT-C", email: "someone-else@example.com" });
  await seedActivation(env.DB, { key: "DLT-A" });
  await seedActivation(env.DB, { key: "DLT-B" });
  await seedActivation(env.DB, { key: "DLT-C" });

  const result = await eraseCustomerByEmail(env.DB, "buyer@example.com");

  assert.equal(result.licenses_deleted, 2, "both case-variant rows deleted");
  assert.equal(result.activations_deleted, 2);

  const remaining = await env.DB
    .prepare(`SELECT COUNT(*) AS n FROM licenses`)
    .first();
  assert.equal(remaining.n, 1, "the other customer is untouched");

  const orphanActivations = await env.DB
    .prepare(`SELECT COUNT(*) AS n FROM license_activations`)
    .first();
  assert.equal(orphanActivations.n, 1);
});

test("eraseCustomerByEmail is a no-op for an unknown email", async () => {
  const env = makeEnv();
  await seedLicense(env.DB, { key: "DLT-A", email: "buyer@example.com" });
  const result = await eraseCustomerByEmail(env.DB, "nobody@example.com");
  assert.equal(result.licenses_deleted, 0);
  assert.equal(result.activations_deleted, 0);
});

test("eraseCustomerByEmail rejects an empty email", async () => {
  const env = makeEnv();
  await assert.rejects(() => eraseCustomerByEmail(env.DB, "   "));
});

test("exportCustomerByEmail returns the customer's licenses only", async () => {
  const env = makeEnv();
  await seedLicense(env.DB, { key: "DLT-A", email: "buyer@example.com" });
  await seedLicense(env.DB, { key: "DLT-C", email: "other@example.com" });
  const data = await exportCustomerByEmail(env.DB, "buyer@example.com");
  assert.equal(data.licenses.length, 1);
  assert.equal(data.licenses[0].license_key, "DLT-A");
});

test("purgeExpiredClicks deletes only expired rows", async () => {
  const env = makeEnv();
  const now = Math.floor(Date.now() / 1000);
  // affiliate_clicks.affiliate_id is a FK -> seed a minimal partner first.
  await env.DB
    .prepare(
      `INSERT INTO affiliates (id, slug, code, display_name, legal_name, email,
         country, terms_version, created_at, updated_at)
       VALUES ('1', 'p', 'P', 'P', 'P Legal', 'p@example.com', 'DE', 'v1', ?, ?)`,
    )
    .bind(now, now)
    .run();
  const insertClick = (id, expiresAt) =>
    env.DB
      .prepare(
        `INSERT INTO affiliate_clicks (id, affiliate_id, ip_hash, user_agent_hash,
           landing_path, campaign, created_at, expires_at)
         VALUES (?, 1, 'iph', 'uah', '/p/x', NULL, ?, ?)`,
      )
      .bind(id, now - 1000, expiresAt)
      .run();
  await insertClick("c-old", now - 10);
  await insertClick("c-fresh", now + 10_000);

  const deleted = await purgeExpiredClicks(env.DB, now);
  assert.equal(deleted, 1);
  const left = await env.DB.prepare(`SELECT COUNT(*) AS n FROM affiliate_clicks`).first();
  assert.equal(left.n, 1);
});

test("purgeStaleActivations removes only long-revoked slots", async () => {
  const env = makeEnv();
  const now = Math.floor(Date.now() / 1000);
  await seedActivation(env.DB, { key: "DLT-active", revokedAt: null });
  await seedActivation(env.DB, { key: "DLT-recent", revokedAt: now - 100 });
  await seedActivation(env.DB, { key: "DLT-stale", revokedAt: now - 200 * 24 * 3600 });

  const deleted = await purgeStaleActivations(env.DB, now);
  assert.equal(deleted, 1, "only the long-revoked slot is purged");
  const left = await env.DB.prepare(`SELECT COUNT(*) AS n FROM license_activations`).first();
  assert.equal(left.n, 2);
});
