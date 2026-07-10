import test from "node:test";
import assert from "node:assert/strict";
import { makeEnv } from "./helpers/fake-d1.mjs";
import { deviationBps, reverseCommission } from "../functions/_affiliate.js";
import { handleAffiliateDisputeClosed } from "../functions/_affiliate_events.js";

const NOW = 1_750_000_000;

async function seedAffiliateWithSettledCommission(env, { settledCents, commissionCents = 200, status = "approved" }) {
  const db = env.DB;
  await db.prepare(
    `INSERT INTO affiliates
      (id, slug, code, display_name, legal_name, email, country, status,
       email_verified_at, terms_version, negative_balance_cents, created_at, updated_at)
     VALUES ('aff1','creator','CREATOR1','Creator','Creator GmbH','creator@example.test','DE','active',?,'2026-07-v1',0,?,?)`,
  ).bind(NOW, NOW, NOW).run();
  await db.prepare(
    `INSERT INTO licenses
      (license_key, tier, email, stripe_checkout_session_id, stripe_payment_intent_id, status, created_at, updated_at)
     VALUES ('DLT-TEST-TEST-TEST','lifetime','buyer@example.test','cs_test_1','pi_test_1','active',?,?)`,
  ).bind(NOW, NOW).run();
  await db.prepare(
    `INSERT INTO affiliate_commissions
      (id, affiliate_id, license_key, stripe_checkout_session_id, stripe_payment_intent_id, status,
       qualified_sale_number, commission_cents, settled_cents, eligible_at, approved_at, created_at, updated_at)
     VALUES ('c1','aff1','DLT-TEST-TEST-TEST','cs_test_1','pi_test_1',?,1,?,?,?,?,?,?)`,
  ).bind(status, commissionCents, settledCents, NOW, NOW, NOW, NOW).run();
}

test("concurrent duplicate refund-webhook deliveries reverse a commission exactly once (no double clawback)", async () => {
  const env = makeEnv();
  await seedAffiliateWithSettledCommission(env, { settledCents: 200, commissionCents: 200, status: "paid" });

  // Simulates two racing Stripe webhook deliveries for the same charge.refunded
  // event both calling reverseCommission() before either has committed its
  // status-flip UPDATE -- Stripe's own at-least-once delivery guarantee makes
  // this a realistic scenario, and two concurrent Cloudflare Worker
  // invocations can genuinely interleave at this granularity.
  const [first, second] = await Promise.all([
    reverseCommission(env, { paymentIntentId: "pi_test_1", reason: "stripe_refunded" }),
    reverseCommission(env, { paymentIntentId: "pi_test_1", reason: "stripe_refunded" }),
  ]);

  const outcomes = [first, second].sort((a, b) => Number(b.reversed) - Number(a.reversed));
  assert.equal(outcomes[0].reversed, true, "exactly one caller must observe the reversal succeeding");
  assert.equal(outcomes[1].reversed, false, "the racing duplicate must observe it as already reversed");
  assert.equal(outcomes[1].reason, "already reversed");

  const affiliate = await env.DB.prepare(`SELECT negative_balance_cents FROM affiliates WHERE id = 'aff1'`).first();
  assert.equal(
    affiliate.negative_balance_cents,
    200,
    "clawback must be applied exactly once (200), not doubled to 400 by the race",
  );

  const ledgerRows = await env.DB.prepare(
    `SELECT COUNT(*) AS count FROM affiliate_ledger WHERE entry_type = 'commission_reversed' AND reference_id = 'c1'`,
  ).first();
  assert.equal(ledgerRows.count, 1, "the reversal must post exactly one ledger entry");
});

test("sequential retries after a real reversal remain fully idempotent", async () => {
  const env = makeEnv();
  await seedAffiliateWithSettledCommission(env, { settledCents: 200, commissionCents: 200, status: "paid" });

  const first = await reverseCommission(env, { paymentIntentId: "pi_test_1", reason: "stripe_refunded" });
  const second = await reverseCommission(env, { paymentIntentId: "pi_test_1", reason: "stripe_refunded" });
  assert.equal(first.reversed, true);
  assert.equal(second.reversed, false);

  const affiliate = await env.DB.prepare(`SELECT negative_balance_cents FROM affiliates WHERE id = 'aff1'`).first();
  assert.equal(affiliate.negative_balance_cents, 200);
});

async function seedReversedDisputedCommission(env, { settledCents, commissionCents = 200 }) {
  const db = env.DB;
  await db.prepare(
    `INSERT INTO affiliates
      (id, slug, code, display_name, legal_name, email, country, status,
       email_verified_at, terms_version, negative_balance_cents, created_at, updated_at)
     VALUES ('aff1','creator','CREATOR1','Creator','Creator GmbH','creator@example.test','DE','active',?,'2026-07-v1',?,?,?)`,
  ).bind(NOW, settledCents, NOW, NOW).run();
  await db.prepare(
    `INSERT INTO licenses
      (license_key, tier, email, stripe_checkout_session_id, stripe_payment_intent_id, status, created_at, updated_at)
     VALUES ('DLT-TEST-TEST-TEST','lifetime','buyer@example.test','cs_test_1','pi_test_1','active',?,?)`,
  ).bind(NOW, NOW).run();
  await db.prepare(
    `INSERT INTO affiliate_commissions
      (id, affiliate_id, license_key, stripe_checkout_session_id, stripe_payment_intent_id, status,
       qualified_sale_number, commission_cents, settled_cents, eligible_at, approved_at,
       reversed_at, reversal_reason, created_at, updated_at)
     VALUES ('c1','aff1','DLT-TEST-TEST-TEST','cs_test_1','pi_test_1','reversed',1,?,?,?,?,?,'stripe_dispute',?,?)`,
  ).bind(commissionCents, settledCents, NOW, NOW, NOW, NOW, NOW).run();
}

test("concurrent duplicate 'dispute closed: won' deliveries restore a commission's balance credit exactly once", async () => {
  const env = makeEnv();
  // Affiliate already carries a 200-cent negative balance from the earlier
  // dispute-open clawback; a won dispute should credit it back exactly once.
  await seedReversedDisputedCommission(env, { settledCents: 200, commissionCents: 200 });

  const dispute = { id: "dp_test_1", status: "won", payment_intent: "pi_test_1" };
  const [first, second] = await Promise.all([
    handleAffiliateDisputeClosed(dispute, env),
    handleAffiliateDisputeClosed(dispute, env),
  ]);

  const outcomes = [first, second].sort((a, b) => Number(b.restored) - Number(a.restored));
  assert.equal(outcomes[0].restored, true);
  assert.equal(outcomes[1].restored, false);

  const affiliate = await env.DB.prepare(`SELECT negative_balance_cents FROM affiliates WHERE id = 'aff1'`).first();
  assert.equal(
    affiliate.negative_balance_cents,
    0,
    "the 200-cent clawback credit must be restored exactly once (200 -> 0), not twice",
  );

  const commission = await env.DB.prepare(`SELECT status FROM affiliate_commissions WHERE id = 'c1'`).first();
  assert.equal(commission.status, "paid");
});

test("deviationBps: exact 5.00% (500 bps) does not exceed the block threshold, 5.01% does", () => {
  const RECONCILIATION_BLOCK_BPS = 500;
  // 1,000,000 vs 950,000 cents differs by exactly 5.00% of the larger value.
  const exactlyFivePercent = deviationBps(1_000_000, 950_000);
  assert.equal(exactlyFivePercent, 500);
  assert.equal(
    exactlyFivePercent > RECONCILIATION_BLOCK_BPS,
    false,
    "exactly 5.00% deviation must NOT trigger the payout freeze (strictly-greater-than semantics)",
  );

  // 1,000,000 vs 949,900 cents differs by just over 5.00% (501 bps).
  const justOverFivePercent = deviationBps(1_000_000, 949_900);
  assert.equal(justOverFivePercent, 501);
  assert.equal(
    justOverFivePercent > RECONCILIATION_BLOCK_BPS,
    true,
    "a deviation of just over 5.00% must trigger the payout freeze",
  );
});
