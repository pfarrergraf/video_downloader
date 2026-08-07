import { sha256Hex } from "./_lib.js";
import { fetchVoidedPurchases } from "./_google_play.js";
import { affiliateFlags, claimAffiliateEvent, completeAffiliateEvent, nowSeconds } from "./_affiliate.js";
import { voidAffiliatePurchase } from "./_affiliate_commissions.js";

const DAY_MILLIS = 24 * 60 * 60 * 1000;

export async function reconcileVoidedAffiliatePurchases(env, limit = 1000) {
  if (!affiliateFlags(env).enabled || !env.DB) return { skipped: true, checked: 0, voided: 0, next_page: false };
  const now = nowSeconds(env);
  const stored = await env.DB.prepare(
    `SELECT window_start_millis, window_end_millis, next_page_token
     FROM affiliate_reconciliation_cursors WHERE source = 'google_voided'`,
  ).first();
  const windowEnd = stored?.window_end_millis || now * 1000;
  const windowStart = stored?.window_start_millis || windowEnd - 30 * DAY_MILLIS;
  const response = await fetchVoidedPurchases(env, {
    startTime: windowStart,
    endTime: windowEnd,
    token: stored?.next_page_token || null,
    maxResults: limit,
  });
  let checked = 0;
  let voided = 0;
  for (const item of response.voidedPurchases || []) {
    if (typeof item.purchaseToken !== "string" || !item.purchaseToken) continue;
    checked += 1;
    const tokenHash = await sha256Hex(item.purchaseToken);
    const eventId = `voided:${tokenHash}:${item.voidedTimeMillis || "unknown"}`;
    const claim = await claimAffiliateEvent(env, {
      source: "google_voided",
      externalEventId: eventId,
      eventType: "voided_purchase",
      payload: { token_hash: tokenHash, order_id: item.orderId || null, voided_time: item.voidedTimeMillis || null },
    });
    if (claim.dedupe) continue;
    if (await voidAffiliatePurchase(env, { purchaseTokenHash: tokenHash, reason: `voided_api_${item.voidedReason ?? "unknown"}` })) voided += 1;
    await completeAffiliateEvent(env, { source: "google_voided", externalEventId: eventId });
  }
  const nextToken = response.tokenPagination?.nextPageToken || null;
  const nextStart = nextToken ? windowStart : windowEnd;
  const nextEnd = nextToken ? windowEnd : now * 1000;
  await env.DB.prepare(
    `INSERT INTO affiliate_reconciliation_cursors
      (source, window_start_millis, window_end_millis, next_page_token, updated_at)
     VALUES ('google_voided', ?, ?, ?, ?)
     ON CONFLICT(source) DO UPDATE SET window_start_millis = excluded.window_start_millis,
       window_end_millis = excluded.window_end_millis, next_page_token = excluded.next_page_token,
       updated_at = excluded.updated_at`,
  ).bind(nextStart, nextEnd, nextToken, now).run();
  return { skipped: false, checked, voided, next_page: Boolean(nextToken) };
}
