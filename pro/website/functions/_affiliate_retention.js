import { affiliateFlags, audit, nowSeconds } from "./_affiliate.js";

const DAY = 24 * 60 * 60;
const CLICK_RETENTION = 90 * DAY;
const ATTRIBUTION_RETENTION = 150 * DAY;

/**
 * Removes only non-financial affiliate data after the documented retention
 * window. Financially linked attribution/click rows are retained because the
 * foreign-key chain is part of payout and dispute evidence. Dry-run is the
 * default so an operator must explicitly approve deletion.
 */
export async function cleanupAffiliateRetention(env, { dryRun = true, now = nowSeconds(env) } = {}) {
  if (!env.DB || !affiliateFlags(env).enabled) return { skipped: true, dry_run: dryRun, deleted_clicks: 0, deleted_attributions: 0 };
  const attributionCutoff = now - ATTRIBUTION_RETENTION;
  const clickCutoff = now - CLICK_RETENTION;
  const staleAttributions = await env.DB.prepare(
    `SELECT COUNT(*) AS count FROM install_attributions i
     WHERE i.attributed_at <= ?
       AND NOT EXISTS (SELECT 1 FROM affiliate_purchases p WHERE p.install_attribution_id = i.id)`,
  ).bind(attributionCutoff).first();
  const staleClicks = await env.DB.prepare(
    `SELECT COUNT(*) AS count FROM referral_clicks c
     WHERE c.created_at <= ?
       AND NOT EXISTS (SELECT 1 FROM install_attributions i WHERE i.click_id = c.click_id)`,
  ).bind(clickCutoff).first();
  const counts = {
    skipped: false,
    dry_run: dryRun,
    eligible_attributions: Number(staleAttributions?.count || 0),
    eligible_clicks: Number(staleClicks?.count || 0),
    deleted_attributions: 0,
    deleted_clicks: 0,
  };
  if (dryRun) return counts;
  const attributionResult = await env.DB.prepare(
    `DELETE FROM install_attributions
     WHERE attributed_at <= ?
       AND NOT EXISTS (SELECT 1 FROM affiliate_purchases p WHERE p.install_attribution_id = install_attributions.id)`,
  ).bind(attributionCutoff).run();
  const clickResult = await env.DB.prepare(
    `DELETE FROM referral_clicks
     WHERE created_at <= ?
       AND NOT EXISTS (SELECT 1 FROM install_attributions i WHERE i.click_id = referral_clicks.click_id)`,
  ).bind(clickCutoff).run();
  counts.deleted_attributions = Number(attributionResult.meta?.changes || 0);
  counts.deleted_clicks = Number(clickResult.meta?.changes || 0);
  await audit(env, "affiliate.retention.cleaned", "affiliate_retention", "scheduled", `${counts.deleted_attributions} attributions; ${counts.deleted_clicks} clicks`, "admin");
  return counts;
}

export { CLICK_RETENTION, ATTRIBUTION_RETENTION };
