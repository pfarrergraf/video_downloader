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

export async function postProcessAffiliateCheckout(session, licenseKey, env) {
  if (!licenseKey) return { attributed: false, reason: "license missing" };
  const result = await handleAffiliateCheckoutPaid(session, licenseKey, env);
  if (!result.attributed) return result;

  const buyerEmail = normalizeEmail(session.customer_details?.email || session.customer_email || "");
  const affiliate = await env.DB.prepare(`SELECT email FROM affiliates WHERE id = ?`)
    .bind(result.affiliate_id)
    .first();
  if (!buyerEmail || normalizeEmail(affiliate?.email) !== buyerEmail) return result;

  const now = nowSeconds();
  const commission = await env.DB.prepare(
    `SELECT id FROM affiliate_commissions WHERE stripe_checkout_session_id = ?`,
  ).bind(session.id).first();
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
  return reverseCommission(env, {
    sessionId: session.id,
    paymentIntentId: objectId(session.payment_intent),
    reason: "stripe_async_payment_failed",
  });
}

export async function handleAffiliateChargeRefunded(charge, env) {
  return reverseCommission(env, {
    paymentIntentId: objectId(charge.payment_intent),
    reason: "stripe_refunded",
  });
}

export async function handleAffiliateDisputeCreated(dispute, env) {
  return reverseCommission(env, {
    paymentIntentId: objectId(dispute.payment_intent),
    reason: "stripe_dispute",
  });
}

export async function handleAffiliateDisputeClosed(dispute, env) {
  const paymentIntentId = objectId(dispute.payment_intent);
  if (!paymentIntentId) return { restored: false, reason: "missing payment intent" };
  if (dispute.status !== "won") {
    return reverseCommission(env, { paymentIntentId, reason: `stripe_dispute_${dispute.status || "lost"}` });
  }

  const commission = await env.DB.prepare(
    `SELECT * FROM affiliate_commissions WHERE stripe_payment_intent_id = ? LIMIT 1`,
  ).bind(paymentIntentId).first();
  if (!commission || commission.status !== "reversed" || !String(commission.reversal_reason || "").startsWith("stripe_dispute")) {
    return { restored: false, reason: "no reversible disputed commission" };
  }

  const now = nowSeconds();
  if (!commission.qualified_sale_number || !commission.commission_cents) {
    await env.DB.prepare(
      `UPDATE affiliate_commissions
          SET status = 'pending', eligible_at = ?, reversed_at = NULL,
              reversal_reason = NULL, updated_at = ?
        WHERE id = ? AND status = 'reversed'`,
    ).bind(now + COMMISSION_REVIEW_SECONDS, now, commission.id).run();
  } else {
    const restoredStatus = Number(commission.settled_cents || 0) >= Number(commission.commission_cents)
      ? "paid"
      : "approved";
    await env.DB.batch([
      env.DB.prepare(
        `UPDATE affiliate_commissions
            SET status = ?, reversed_at = NULL, reversal_reason = NULL, updated_at = ?
          WHERE id = ? AND status = 'reversed'`,
      ).bind(restoredStatus, now, commission.id),
      env.DB.prepare(
        `UPDATE affiliates
            SET negative_balance_cents = MAX(negative_balance_cents - ?, 0),
                updated_at = ?, version = version + 1
          WHERE id = ?`,
      ).bind(Number(commission.settled_cents || 0), now, commission.affiliate_id),
    ]);
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
