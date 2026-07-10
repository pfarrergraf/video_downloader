import {
  COMMISSION_REVIEW_SECONDS,
  appendAudit,
  appendLedger,
  handleAffiliateCheckoutPaid,
  normalizeEmail,
  nowSeconds,
  reverseCommission,
} from "./_affiliate.js";

function objectId(value) {
  if (!value) return null;
  return typeof value === "string" ? value : value.id || null;
}

async function updateCheckoutStatusByPaymentIntent(env, paymentIntentId, status, now) {
  if (!paymentIntentId) return;
  await env.DB.prepare(
    `UPDATE affiliate_checkout_intents
        SET payment_status = ?, finalized_at = COALESCE(finalized_at, ?)
      WHERE stripe_checkout_session_id IN (
        SELECT stripe_checkout_session_id FROM licenses WHERE stripe_payment_intent_id = ?
      )`,
  ).bind(status, now, paymentIntentId).run();
}

export async function postProcessAffiliateCheckout(session, licenseKey, env) {
  if (!licenseKey) return { attributed: false, reason: "license missing" };
  const result = await handleAffiliateCheckoutPaid(session, licenseKey, env);
  if (!result.attributed) return result;

  const now = nowSeconds();
  const paymentIntentId = objectId(session.payment_intent);

  // Stripe sends checkout.session.completed before delayed payment methods such
  // as SEPA have actually cleared. Keep license attribution, but remove the
  // helper's provisional commission row. async_payment_succeeded will call this
  // function again and create the real 30-day commission only after money exists.
  if (session.payment_status !== "paid") {
    const draft = await env.DB.prepare(
      `SELECT id FROM affiliate_commissions
        WHERE stripe_checkout_session_id = ? AND qualified_sale_number IS NULL
          AND settled_cents = 0 LIMIT 1`,
    ).bind(session.id).first();
    const statements = [
      env.DB.prepare(
        `UPDATE affiliate_checkout_intents
            SET payment_status = 'created', finalized_at = NULL
          WHERE stripe_checkout_session_id = ?`,
      ).bind(session.id),
    ];
    if (draft) {
      statements.push(
        env.DB.prepare(
          `UPDATE licenses SET affiliate_commission_id = NULL, updated_at = ?
            WHERE license_key = ?`,
        ).bind(now, licenseKey),
        env.DB.prepare(
          `DELETE FROM affiliate_commissions
            WHERE id = ? AND qualified_sale_number IS NULL AND settled_cents = 0`,
        ).bind(draft.id),
      );
    }
    await env.DB.batch(statements);
    return { attributed: true, awaiting_payment: true, affiliate_id: result.affiliate_id };
  }

  const affiliate = await env.DB.prepare(`SELECT email, status FROM affiliates WHERE id = ?`)
    .bind(result.affiliate_id)
    .first();
  let commission = await env.DB.prepare(
    `SELECT id, status FROM affiliate_commissions WHERE stripe_checkout_session_id = ?`,
  ).bind(session.id).first();

  // A partner can be suspended after the customer opened Checkout but before
  // Stripe confirms payment. Keep the conversion trail complete, but make it
  // explicitly non-payable instead of leaving a license without a matching
  // commission row (which would otherwise look like a reconciliation defect).
  if (!commission && affiliate?.status !== "active") {
    const rejectedId = crypto.randomUUID();
    await env.DB.prepare(
      `INSERT OR IGNORE INTO affiliate_commissions
        (id, affiliate_id, license_key, stripe_checkout_session_id,
         stripe_payment_intent_id, status, eligible_at, reversed_at,
         reversal_reason, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, 'rejected', ?, ?, 'affiliate_not_active', ?, ?)`,
    ).bind(
      rejectedId,
      result.affiliate_id,
      licenseKey,
      session.id,
      paymentIntentId,
      now,
      now,
      now,
      now,
    ).run();
    commission = await env.DB.prepare(
      `SELECT id, status FROM affiliate_commissions WHERE stripe_checkout_session_id = ?`,
    ).bind(session.id).first();
    if (commission) {
      await env.DB.prepare(
        `UPDATE licenses
            SET affiliate_commission_id = COALESCE(affiliate_commission_id, ?), updated_at = ?
          WHERE license_key = ?`,
      ).bind(commission.id, now, licenseKey).run();
      await appendAudit(env, "system", "inactive_partner_conversion_rejected", "commission", commission.id, {
        checkout_session_id: session.id,
        affiliate_status: affiliate?.status || "missing",
      });
    }
    return { attributed: true, rejected: true, reason: "affiliate_not_active" };
  }

  const buyerEmail = normalizeEmail(session.customer_details?.email || session.customer_email || "");
  if (!buyerEmail || normalizeEmail(affiliate?.email) !== buyerEmail) return result;

  if (commission) {
    await env.DB.batch([
      env.DB.prepare(
        `UPDATE affiliate_commissions
            SET status = 'rejected', reversal_reason = 'self_referral', reversed_at = ?, updated_at = ?
          WHERE id = ? AND status = 'pending'`,
      ).bind(now, now, commission.id),
      env.DB.prepare(
        `UPDATE licenses SET affiliate_commission_id = NULL, updated_at = ? WHERE license_key = ?`,
      ).bind(now, licenseKey),
    ]);
    await appendAudit(env, "system", "self_referral_rejected", "commission", commission.id, {
      checkout_session_id: session.id,
    });
  }
  return { attributed: true, rejected: true, reason: "self_referral" };
}

export async function handleAffiliatePaymentFailure(session, env) {
  const now = nowSeconds();
  const commission = await env.DB.prepare(
    `SELECT id, qualified_sale_number, settled_cents
       FROM affiliate_commissions WHERE stripe_checkout_session_id = ? LIMIT 1`,
  ).bind(session.id).first();
  await env.DB.prepare(
    `UPDATE affiliate_checkout_intents
        SET payment_status = 'failed', finalized_at = COALESCE(finalized_at, ?)
      WHERE stripe_checkout_session_id = ?`,
  ).bind(now, session.id).run();
  const result = await reverseCommission(env, {
    sessionId: session.id,
    paymentIntentId: objectId(session.payment_intent),
    reason: "stripe_async_payment_failed",
  });

  // Defensive cleanup for legacy/staged rows created before the paid-only rule.
  if (commission && !commission.qualified_sale_number && Number(commission.settled_cents || 0) === 0) {
    await env.DB.batch([
      env.DB.prepare(
        `UPDATE licenses SET affiliate_commission_id = NULL, updated_at = ?
          WHERE stripe_checkout_session_id = ?`,
      ).bind(now, session.id),
      env.DB.prepare(
        `DELETE FROM affiliate_commissions
          WHERE id = ? AND qualified_sale_number IS NULL AND settled_cents = 0`,
      ).bind(commission.id),
    ]);
    return { ...result, unpaid_draft_removed: true };
  }
  return result;
}

export async function handleAffiliateChargeRefunded(charge, env) {
  const paymentIntentId = objectId(charge.payment_intent);
  const now = nowSeconds();
  const fullyRefunded = charge.refunded === true ||
    (Number(charge.amount_refunded || 0) >= Number(charge.amount || 0) && Number(charge.amount || 0) > 0);
  if (paymentIntentId) {
    await updateCheckoutStatusByPaymentIntent(env, paymentIntentId, fullyRefunded ? "refunded" : "paid", now);
    if (fullyRefunded) {
      await env.DB.prepare(
        `UPDATE licenses SET status = 'canceled', updated_at = ?
          WHERE stripe_payment_intent_id = ? AND status <> 'canceled'`,
      ).bind(now, paymentIntentId).run();
    }
  }
  // Any refund removes the affiliate reward. A partial goodwill refund may
  // leave the customer's license active, but it never funds a full commission.
  return reverseCommission(env, {
    paymentIntentId,
    reason: fullyRefunded ? "stripe_refunded" : "stripe_partially_refunded",
  });
}

export async function handleAffiliateDisputeCreated(dispute, env) {
  const paymentIntentId = objectId(dispute.payment_intent);
  const now = nowSeconds();
  await updateCheckoutStatusByPaymentIntent(env, paymentIntentId, "disputed", now);
  return reverseCommission(env, {
    paymentIntentId,
    reason: "stripe_dispute",
  });
}

export async function handleAffiliateDisputeClosed(dispute, env) {
  const paymentIntentId = objectId(dispute.payment_intent);
  if (!paymentIntentId) return { restored: false, reason: "missing payment intent" };
  const now = nowSeconds();
  if (dispute.status !== "won") {
    await updateCheckoutStatusByPaymentIntent(env, paymentIntentId, "disputed", now);
    return reverseCommission(env, { paymentIntentId, reason: `stripe_dispute_${dispute.status || "lost"}` });
  }

  await updateCheckoutStatusByPaymentIntent(env, paymentIntentId, "paid", now);
  const commission = await env.DB.prepare(
    `SELECT * FROM affiliate_commissions WHERE stripe_payment_intent_id = ? LIMIT 1`,
  ).bind(paymentIntentId).first();
  if (!commission || commission.status !== "reversed" || !String(commission.reversal_reason || "").startsWith("stripe_dispute")) {
    return { restored: false, reason: "no reversible disputed commission" };
  }

  // As in reverseCommission, a concurrent/duplicate "dispute closed: won"
  // delivery for the same event must not apply its balance/ledger side
  // effects twice. Both restoration branches now check the row-change count
  // of the status-flipping UPDATE (the only statement whose WHERE clause
  // pins to the pre-restoration 'reversed' state) before doing anything else,
  // so a raced duplicate observes 0 changes and stops -- otherwise the
  // negative-balance credit below (`MAX(x - settled, 0)`) is read against the
  // live column value on each call and would double-credit the partner if
  // both duplicates ran their UPDATEs back to back.
  if (!commission.qualified_sale_number || !commission.commission_cents) {
    const pendingRestore = await env.DB.prepare(
      `UPDATE affiliate_commissions
          SET status = 'pending', eligible_at = ?, reversed_at = NULL,
              reversal_reason = NULL, updated_at = ?
        WHERE id = ? AND status = 'reversed'`,
    ).bind(now + COMMISSION_REVIEW_SECONDS, now, commission.id).run();
    if ((pendingRestore.meta?.changes || 0) !== 1) {
      return { restored: false, reason: "already restored" };
    }
  } else {
    const restoredStatus = Number(commission.settled_cents || 0) >= Number(commission.commission_cents)
      ? "paid"
      : "approved";
    const statusRestore = await env.DB.prepare(
      `UPDATE affiliate_commissions
          SET status = ?, reversed_at = NULL, reversal_reason = NULL, updated_at = ?
        WHERE id = ? AND status = 'reversed'`,
    ).bind(restoredStatus, now, commission.id).run();
    if ((statusRestore.meta?.changes || 0) !== 1) {
      return { restored: false, reason: "already restored" };
    }
    await env.DB.prepare(
      `UPDATE affiliates
          SET negative_balance_cents = MAX(negative_balance_cents - ?, 0),
              updated_at = ?, version = version + 1
        WHERE id = ?`,
    ).bind(Number(commission.settled_cents || 0), now, commission.affiliate_id).run();
    try {
      await appendLedger(
        env,
        commission.affiliate_id,
        "manual_adjustment",
        Number(commission.commission_cents),
        "stripe_dispute",
        dispute.id,
        "stripe-webhook",
      );
    } catch (error) {
      if (!String(error.message || error).includes("UNIQUE")) throw error;
    }
  }

  await appendAudit(env, "stripe-webhook", "won_dispute_restored", "commission", commission.id, {
    dispute_id: dispute.id,
    payment_intent_id: paymentIntentId,
  });
  return { restored: true, commission_id: commission.id };
}
