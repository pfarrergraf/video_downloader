import {
  RECONCILIATION_BLOCK_BPS,
  nowSeconds,
  sha256Hex,
} from "./_affiliate.js";

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

async function hashObject(value) {
  return sha256Hex(JSON.stringify(canonicalize(value)));
}

function integer(value) {
  return Number.parseInt(value || 0, 10) || 0;
}

export function deviationBps(left, right) {
  const a = integer(left);
  const b = integer(right);
  if (a === 0 && b === 0) return 0;
  return Math.round((Math.abs(a - b) * 10000) / Math.max(Math.abs(a), Math.abs(b), 1));
}

async function allRows(env, sql, pageSize = 500) {
  const rows = [];
  let offset = 0;
  while (true) {
    const page = await env.DB.prepare(`${sql} LIMIT ? OFFSET ?`).bind(pageSize, offset).all();
    const batch = page.results || [];
    rows.push(...batch);
    if (batch.length < pageSize) return rows;
    offset += batch.length;
    if (offset > 1000000) throw new Error("Integrity scan exceeded one million rows");
  }
}

async function verifyChain(rows, hashColumn, payloadForRow) {
  let previousHash = null;
  for (const row of rows) {
    if ((row.previous_hash || null) !== previousHash) {
      return { ok: false, reason: `broken_previous_hash_at:${row.id}` };
    }
    const expected = await hashObject(payloadForRow(row));
    if (expected !== row[hashColumn]) {
      return { ok: false, reason: `invalid_hash_at:${row.id}` };
    }
    previousHash = row[hashColumn];
  }
  return { ok: true, count: rows.length, tail_hash: previousHash };
}

async function verifyLedgerChain(env) {
  const rows = await allRows(
    env,
    `SELECT id, affiliate_id, entry_type, amount_cents, reference_type, reference_id,
            created_by, previous_hash, entry_hash, created_at
       FROM affiliate_ledger ORDER BY created_at ASC, id ASC`,
  );
  return verifyChain(rows, "entry_hash", (row) => ({
    id: row.id,
    affiliate_id: row.affiliate_id,
    entry_type: row.entry_type,
    amount_cents: integer(row.amount_cents),
    reference_type: row.reference_type,
    reference_id: row.reference_id,
    created_by: row.created_by,
    previous_hash: row.previous_hash || null,
    created_at: integer(row.created_at),
  }));
}

async function verifyAuditChain(env) {
  const rows = await allRows(
    env,
    `SELECT id, actor, action, entity_type, entity_id, details_json,
            previous_hash, entry_hash, created_at
       FROM affiliate_audit_log ORDER BY created_at ASC, id ASC`,
  );
  return verifyChain(rows, "entry_hash", (row) => ({
    id: row.id,
    actor: row.actor,
    action: row.action,
    entity_type: row.entity_type,
    entity_id: row.entity_id,
    details_json: row.details_json,
    previous_hash: row.previous_hash || null,
    created_at: integer(row.created_at),
  }));
}

async function verifyReconciliationChain(env) {
  const rows = await allRows(
    env,
    `SELECT id, status, valid_license_count, stripe_paid_session_count,
            stripe_paid_ever_count, recognized_revenue_cents,
            expected_commission_cents, recorded_liability_cents,
            ledger_liability_cents, paid_out_cents,
            max_possible_commission_cents, revenue_deviation_bps,
            count_deviation_bps, commission_deviation_bps,
            ledger_deviation_bps, reasons_json, previous_hash,
            snapshot_hash, created_at
       FROM affiliate_reconciliation_snapshots ORDER BY created_at ASC, id ASC`,
  );
  return verifyChain(rows, "snapshot_hash", (row) => ({
    id: row.id,
    status: row.status,
    valid_license_count: integer(row.valid_license_count),
    stripe_paid_session_count: integer(row.stripe_paid_session_count),
    stripe_paid_ever_count: integer(row.stripe_paid_ever_count),
    recognized_revenue_cents: integer(row.recognized_revenue_cents),
    expected_commission_cents: integer(row.expected_commission_cents),
    recorded_liability_cents: integer(row.recorded_liability_cents),
    ledger_liability_cents: integer(row.ledger_liability_cents),
    paid_out_cents: integer(row.paid_out_cents),
    max_possible_commission_cents: integer(row.max_possible_commission_cents),
    revenue_deviation_bps: integer(row.revenue_deviation_bps),
    count_deviation_bps: integer(row.count_deviation_bps),
    commission_deviation_bps: integer(row.commission_deviation_bps),
    ledger_deviation_bps: integer(row.ledger_deviation_bps),
    reasons_json: row.reasons_json,
    previous_hash: row.previous_hash || null,
    created_at: integer(row.created_at),
  }));
}

async function verifyIntegrityCheckChain(env) {
  const rows = await allRows(
    env,
    `SELECT id, status, hard_failures_json, deviation_failures_json,
            metrics_json, previous_hash, check_hash, created_at
       FROM affiliate_integrity_checks ORDER BY created_at ASC, id ASC`,
  );
  return verifyChain(rows, "check_hash", (row) => ({
    id: row.id,
    status: row.status,
    hard_failures_json: row.hard_failures_json,
    deviation_failures_json: row.deviation_failures_json,
    metrics_json: row.metrics_json,
    previous_hash: row.previous_hash || null,
    created_at: integer(row.created_at),
  }));
}

async function scalar(env, sql) {
  const row = await env.DB.prepare(sql).first();
  return integer(row?.value);
}

async function collectFinanceMetrics(env) {
  const [
    attributedLicenses,
    commissionRows,
    qualifiedCommissions,
    qualifiedCommissionCents,
    currentEarnedCents,
    paidOutCents,
    ledgerBalanceCents,
    scheduleMismatches,
    affiliateCounterMismatches,
    affiliateApprovedAmountMismatches,
    affiliatePaidAmountMismatches,
    allocationMismatches,
    payoutAllocationMismatches,
    missingLedgerCommissionApprovals,
    missingLedgerCommissionReversals,
    missingLedgerPayouts,
    orphanLedgerReferences,
    invalidPaidPayouts,
    blockedSnapshotPayouts,
    duplicatePaymentIntents,
  ] = await Promise.all([
    scalar(env, `SELECT COUNT(*) AS value FROM licenses WHERE affiliate_id IS NOT NULL`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_commissions`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_commissions WHERE qualified_sale_number IS NOT NULL`),
    scalar(env, `SELECT COALESCE(SUM(commission_cents), 0) AS value FROM affiliate_commissions WHERE qualified_sale_number IS NOT NULL`),
    scalar(env, `SELECT COALESCE(SUM(commission_cents), 0) AS value FROM affiliate_commissions WHERE status IN ('approved', 'paid')`),
    scalar(env, `SELECT COALESCE(SUM(amount_cents), 0) AS value FROM affiliate_payouts WHERE status = 'paid'`),
    scalar(env, `SELECT COALESCE(SUM(amount_cents), 0) AS value FROM affiliate_ledger`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_commissions WHERE qualified_sale_number IS NOT NULL AND commission_cents <> CASE WHEN qualified_sale_number BETWEEN 1 AND 10 THEN 200 WHEN qualified_sale_number BETWEEN 11 AND 50 THEN 250 WHEN qualified_sale_number BETWEEN 51 AND 100 THEN 300 WHEN qualified_sale_number BETWEEN 101 AND 500 THEN 350 WHEN qualified_sale_number >= 501 THEN 400 ELSE -1 END`),
    scalar(env, `SELECT COUNT(*) AS value FROM (SELECT a.id FROM affiliates a LEFT JOIN affiliate_commissions c ON c.affiliate_id = a.id AND c.qualified_sale_number IS NOT NULL GROUP BY a.id HAVING a.approved_sale_count <> COUNT(c.id) OR a.approved_sale_count <> COALESCE(MAX(c.qualified_sale_number), 0))`),
    scalar(env, `SELECT COUNT(*) AS value FROM (SELECT a.id FROM affiliates a LEFT JOIN affiliate_commissions c ON c.affiliate_id = a.id AND c.qualified_sale_number IS NOT NULL GROUP BY a.id HAVING a.lifetime_approved_cents <> COALESCE(SUM(c.commission_cents), 0))`),
    scalar(env, `SELECT COUNT(*) AS value FROM (SELECT a.id FROM affiliates a LEFT JOIN affiliate_payouts p ON p.affiliate_id = a.id AND p.status = 'paid' GROUP BY a.id HAVING a.lifetime_paid_cents <> COALESCE(SUM(p.amount_cents), 0))`),
    scalar(env, `SELECT COUNT(*) AS value FROM (SELECT c.id FROM affiliate_commissions c LEFT JOIN affiliate_payout_allocations a ON a.commission_id = c.id GROUP BY c.id HAVING c.settled_cents <> COALESCE(SUM(a.amount_cents), 0) OR c.settled_cents > COALESCE(c.commission_cents, 0))`),
    scalar(env, `SELECT COUNT(*) AS value FROM (SELECT p.id FROM affiliate_payouts p LEFT JOIN affiliate_payout_allocations a ON a.payout_id = p.id GROUP BY p.id HAVING COALESCE(SUM(a.amount_cents), 0) - p.negative_balance_applied_cents <> p.amount_cents)`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_commissions c LEFT JOIN affiliate_ledger l ON l.entry_type = 'commission_approved' AND l.reference_type = 'commission' AND l.reference_id = c.id AND l.amount_cents = c.commission_cents WHERE c.qualified_sale_number IS NOT NULL AND l.id IS NULL`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_commissions c LEFT JOIN affiliate_ledger l ON l.entry_type = 'commission_reversed' AND l.reference_type = 'commission' AND l.reference_id = c.id AND l.amount_cents = -c.commission_cents WHERE c.status = 'reversed' AND c.qualified_sale_number IS NOT NULL AND l.id IS NULL`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_payouts p LEFT JOIN affiliate_ledger l ON l.entry_type = 'payout_paid' AND l.reference_type = 'payout' AND l.reference_id = p.id AND l.amount_cents = -p.amount_cents WHERE p.status = 'paid' AND l.id IS NULL`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_ledger l WHERE (l.reference_type = 'commission' AND NOT EXISTS (SELECT 1 FROM affiliate_commissions c WHERE c.id = l.reference_id)) OR (l.reference_type = 'payout' AND NOT EXISTS (SELECT 1 FROM affiliate_payouts p WHERE p.id = l.reference_id))`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_payouts WHERE status = 'paid' AND (external_reference IS NULL OR LENGTH(TRIM(external_reference)) < 3 OR paid_at IS NULL OR approved_by IS NULL)`),
    scalar(env, `SELECT COUNT(*) AS value FROM affiliate_payouts p JOIN affiliate_reconciliation_snapshots r ON r.id = p.reconciliation_snapshot_id WHERE p.status IN ('prepared','approved','paid') AND r.status <> 'ok'`),
    scalar(env, `SELECT COUNT(*) AS value FROM (SELECT stripe_payment_intent_id FROM affiliate_commissions WHERE stripe_payment_intent_id IS NOT NULL GROUP BY stripe_payment_intent_id HAVING COUNT(*) > 1)`),
  ]);

  const absoluteCeilingCents = attributedLicenses * 400;
  const expectedLedgerBalanceCents = currentEarnedCents - paidOutCents;
  const latestReconciliation = await env.DB.prepare(
    `SELECT * FROM affiliate_reconciliation_snapshots ORDER BY created_at DESC, id DESC LIMIT 1`,
  ).first();

  return {
    attributed_licenses: attributedLicenses,
    commission_rows: commissionRows,
    qualified_commissions: qualifiedCommissions,
    qualified_commission_cents: qualifiedCommissionCents,
    current_earned_cents: currentEarnedCents,
    paid_out_cents: paidOutCents,
    ledger_balance_cents: ledgerBalanceCents,
    expected_ledger_balance_cents: expectedLedgerBalanceCents,
    absolute_ceiling_cents: absoluteCeilingCents,
    schedule_mismatches: scheduleMismatches,
    affiliate_counter_mismatches: affiliateCounterMismatches,
    affiliate_approved_amount_mismatches: affiliateApprovedAmountMismatches,
    affiliate_paid_amount_mismatches: affiliatePaidAmountMismatches,
    allocation_mismatches: allocationMismatches,
    payout_allocation_mismatches: payoutAllocationMismatches,
    missing_ledger_commission_approvals: missingLedgerCommissionApprovals,
    missing_ledger_commission_reversals: missingLedgerCommissionReversals,
    missing_ledger_payouts: missingLedgerPayouts,
    orphan_ledger_references: orphanLedgerReferences,
    invalid_paid_payouts: invalidPaidPayouts,
    blocked_snapshot_payouts: blockedSnapshotPayouts,
    duplicate_payment_intents: duplicatePaymentIntents,
    latest_reconciliation: latestReconciliation || null,
    license_commission_count_deviation_bps: deviationBps(attributedLicenses, commissionRows),
    ledger_deviation_bps: deviationBps(ledgerBalanceCents, expectedLedgerBalanceCents),
  };
}

async function appendIntegrityCheck(env, status, hardFailures, deviationFailures, metrics) {
  const previous = await env.DB.prepare(
    `SELECT check_hash FROM affiliate_integrity_checks ORDER BY created_at DESC, id DESC LIMIT 1`,
  ).first();
  const id = crypto.randomUUID();
  const createdAt = nowSeconds();
  const record = {
    id,
    status,
    hard_failures_json: JSON.stringify(hardFailures),
    deviation_failures_json: JSON.stringify(deviationFailures),
    metrics_json: JSON.stringify(metrics),
    previous_hash: previous?.check_hash || null,
    created_at: createdAt,
  };
  const checkHash = await hashObject(record);
  await env.DB.prepare(
    `INSERT INTO affiliate_integrity_checks
      (id, status, hard_failures_json, deviation_failures_json, metrics_json,
       previous_hash, check_hash, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    id,
    status,
    record.hard_failures_json,
    record.deviation_failures_json,
    record.metrics_json,
    record.previous_hash,
    checkHash,
    createdAt,
  ).run();
  return { id, check_hash: checkHash, created_at: createdAt };
}

export async function runIntegrityGate(env, actor = "system") {
  const [ledgerChain, auditChain, reconciliationChain, integrityChain, metrics] = await Promise.all([
    verifyLedgerChain(env),
    verifyAuditChain(env),
    verifyReconciliationChain(env),
    verifyIntegrityCheckChain(env),
    collectFinanceMetrics(env),
  ]);

  const hardFailures = [];
  if (!ledgerChain.ok) hardFailures.push(`ledger_hash_chain:${ledgerChain.reason}`);
  if (!auditChain.ok) hardFailures.push(`audit_hash_chain:${auditChain.reason}`);
  if (!reconciliationChain.ok) hardFailures.push(`reconciliation_hash_chain:${reconciliationChain.reason}`);
  if (!integrityChain.ok) hardFailures.push(`integrity_hash_chain:${integrityChain.reason}`);
  for (const [name, value] of Object.entries(metrics)) {
    if (name.endsWith("_mismatches") || name.startsWith("missing_") || name.startsWith("orphan_") || name.startsWith("invalid_") || name.startsWith("blocked_") || name.startsWith("duplicate_")) {
      if (integer(value) > 0) hardFailures.push(`${name}:${value}`);
    }
  }
  if (metrics.paid_out_cents > metrics.absolute_ceiling_cents) {
    hardFailures.push("paid_out_exceeds_four_euro_per_attributed_license_ceiling");
  }
  if (metrics.qualified_commission_cents > metrics.absolute_ceiling_cents) {
    hardFailures.push("qualified_commissions_exceed_absolute_license_ceiling");
  }
  if (metrics.paid_out_cents > metrics.qualified_commission_cents) {
    hardFailures.push("paid_out_exceeds_all_qualified_commissions");
  }
  if (!metrics.latest_reconciliation || metrics.latest_reconciliation.status !== "ok") {
    hardFailures.push("no_fresh_successful_reconciliation");
  }

  const deviationFailures = [];
  if (metrics.license_commission_count_deviation_bps > RECONCILIATION_BLOCK_BPS) {
    deviationFailures.push("affiliate_license_commission_count_deviation_over_5_percent");
  }
  if (metrics.ledger_deviation_bps > RECONCILIATION_BLOCK_BPS) {
    deviationFailures.push("independent_ledger_deviation_over_5_percent");
  }
  const reconciliation = metrics.latest_reconciliation;
  if (reconciliation) {
    for (const [field, reason] of [
      ["revenue_deviation_bps", "stripe_revenue_deviation_over_5_percent"],
      ["count_deviation_bps", "stripe_license_count_deviation_over_5_percent"],
      ["commission_deviation_bps", "commission_schedule_deviation_over_5_percent"],
      ["ledger_deviation_bps", "reconciliation_ledger_deviation_over_5_percent"],
    ]) {
      if (integer(reconciliation[field]) > RECONCILIATION_BLOCK_BPS) deviationFailures.push(reason);
    }
  }

  const status = hardFailures.length || deviationFailures.length ? "blocked" : "ok";
  const check = await appendIntegrityCheck(env, status, hardFailures, deviationFailures, {
    ...metrics,
    latest_reconciliation: metrics.latest_reconciliation?.id || null,
    chains: {
      ledger: ledgerChain,
      audit: auditChain,
      reconciliation: reconciliationChain,
      integrity: integrityChain,
    },
    actor,
  });

  const now = nowSeconds();
  const reason = [...hardFailures, ...deviationFailures].join(", ");
  await env.DB.prepare(
    `UPDATE affiliate_controls
        SET payout_frozen = ?, freeze_reason = ?, frozen_at = ?, updated_at = ?
      WHERE id = 'global'`,
  ).bind(status === "blocked" ? 1 : 0, reason, status === "blocked" ? now : null, now).run();

  return {
    id: check.id,
    status,
    hard_failures: hardFailures,
    deviation_failures: deviationFailures,
    metrics,
    chains: {
      ledger: ledgerChain,
      audit: auditChain,
      reconciliation: reconciliationChain,
      integrity: integrityChain,
    },
  };
}

export async function requireIntegrityForPayout(env, actor) {
  const result = await runIntegrityGate(env, actor);
  if (result.status !== "ok") {
    const error = new Error("Affiliate payout integrity gate is blocked");
    error.code = "payouts_frozen";
    error.integrity = result;
    throw error;
  }
  return result;
}
