// GDPR data-lifecycle helpers: subject erasure (Art. 17) for customers, and
// retention cleanup of pseudonymous tracking rows that otherwise accumulate
// forever. Pure functions over a D1 handle so they run under the fake-D1 test
// harness (tests/helpers/fake-d1.mjs) against the real schema.
//
// Scope note: this covers the *customer* (buyer) side - the `licenses` table
// has no append-only trigger, so a buyer's PII (email + Stripe ids) can be
// deleted outright. Partner/affiliate erasure is deliberately NOT done here:
// the affiliate ledger/audit tables are append-only by DB trigger (financial
// record-keeping obligation) and require anonymization, not deletion - see
// docs and RESIDUAL_RISK notes.
import { sha256Hex } from "./_lib.js";
import { normalizeEmail } from "./_affiliate.js";

/**
 * Erase all data tied to a customer's email: their license row(s) (email +
 * Stripe ids) and the hashed device-activation rows for those keys.
 * Case-insensitive on email. Returns counts for the operator's DSAR record.
 */
export async function eraseCustomerByEmail(db, rawEmail) {
  const email = normalizeEmail(rawEmail);
  if (!email) throw new Error("email required");

  // Fetch the keys first so we can purge their hashed activation rows - the
  // activations table stores only SHA-256(key), so we must re-hash before the
  // license rows are gone.
  const { results: keyRows } = await db
    .prepare(`SELECT license_key FROM licenses WHERE lower(email) = ?`)
    .bind(email)
    .all();

  let activationsDeleted = 0;
  for (const row of keyRows) {
    const keyHash = await sha256Hex(row.license_key);
    const res = await db
      .prepare(`DELETE FROM license_activations WHERE license_key_hash = ?`)
      .bind(keyHash)
      .run();
    activationsDeleted += res.meta.changes;
  }

  const lic = await db
    .prepare(`DELETE FROM licenses WHERE lower(email) = ?`)
    .bind(email)
    .run();

  return {
    email,
    licenses_deleted: lic.meta.changes,
    activations_deleted: activationsDeleted,
    keys_found: keyRows.length,
  };
}

/**
 * Export everything the backend holds about a customer email (DSAR access
 * request, Art. 15). Read-only.
 */
export async function exportCustomerByEmail(db, rawEmail) {
  const email = normalizeEmail(rawEmail);
  if (!email) throw new Error("email required");
  const { results: licenses } = await db
    .prepare(
      `SELECT license_key, tier, email, stripe_customer_id, stripe_subscription_id,
              stripe_checkout_session_id, status, current_period_end, created_at, updated_at
         FROM licenses WHERE lower(email) = ?`,
    )
    .bind(email)
    .all();
  return { email, licenses };
}

/**
 * Delete expired affiliate_clicks (they carry a salted IP/UA hash and an
 * expires_at, but nothing ever purged them). Returns rows removed.
 */
export async function purgeExpiredClicks(db, nowSeconds) {
  const res = await db
    .prepare(`DELETE FROM affiliate_clicks WHERE expires_at < ?`)
    .bind(nowSeconds)
    .run();
  return res.meta.changes;
}

/**
 * Delete license_activations that were revoked long ago (stale device slots).
 * Keeps the active slot rows; only removes ones already revoked before the
 * cutoff, so activation history doesn't grow without bound.
 */
export async function purgeStaleActivations(db, nowSeconds, staleSeconds = 90 * 24 * 3600) {
  const cutoff = nowSeconds - staleSeconds;
  const res = await db
    .prepare(`DELETE FROM license_activations WHERE revoked_at IS NOT NULL AND revoked_at < ?`)
    .bind(cutoff)
    .run();
  return res.meta.changes;
}
