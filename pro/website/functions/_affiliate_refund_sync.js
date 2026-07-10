import { nowSeconds } from "./_affiliate.js";

function objectId(value) {
  if (!value) return null;
  return typeof value === "string" ? value : value.id || null;
}

/**
 * Keep locally recognized revenue equal to Stripe's remaining charge amount.
 * Full refunds revoke the license; partial refunds retain the license but never
 * retain the affiliate reward (handled separately by _affiliate_events.js).
 */
export async function syncAffiliateRefundRevenue(charge, env) {
  const paymentIntentId = objectId(charge.payment_intent);
  if (!paymentIntentId) return { synced: false, reason: "missing_payment_intent" };

  const amount = Math.max(0, Number(charge.amount || 0));
  const refunded = Math.max(0, Number(charge.amount_refunded || 0));
  const netAmount = Math.max(0, amount - refunded);
  const fullyRefunded = charge.refunded === true || (amount > 0 && refunded >= amount);
  const now = nowSeconds();

  await env.DB.batch([
    env.DB.prepare(
      `UPDATE licenses
          SET amount_total_cents = ?,
              status = CASE WHEN ? = 1 THEN 'canceled' ELSE status END,
              updated_at = ?
        WHERE stripe_payment_intent_id = ?`,
    ).bind(netAmount, fullyRefunded ? 1 : 0, now, paymentIntentId),
    env.DB.prepare(
      `UPDATE affiliate_checkout_intents
          SET amount_total_cents = ?, payment_status = ?,
              finalized_at = COALESCE(finalized_at, ?)
        WHERE stripe_checkout_session_id IN (
          SELECT stripe_checkout_session_id FROM licenses
           WHERE stripe_payment_intent_id = ?
        )`,
    ).bind(netAmount, fullyRefunded ? "refunded" : "paid", now, paymentIntentId),
  ]);

  return { synced: true, net_amount_cents: netAmount, fully_refunded: fullyRefunded };
}
