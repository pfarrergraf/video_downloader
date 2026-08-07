import { affiliateDisabledResponse, affiliateFlags, createReferralClaim, recordReferralClick } from "../../_affiliate.js";

export async function onRequestGet({ params, env }) {
  const flags = affiliateFlags(env);
  if (!flags.enabled || !flags.redirect || !env.DB) return affiliateDisabledResponse();
  let click;
  try { click = await recordReferralClick(env, params?.affiliateCode, params?.campaignSlug); }
  catch (error) {
    const status = Number(error?.status) || 503;
    return new Response(status === 429 ? "Referral link rate limited" : "Referral service unavailable", { status, headers: { "Cache-Control": "no-store" } });
  }
  if (!click) return new Response("Referral link not found", { status: 404, headers: { "Cache-Control": "no-store" } });
  let claim;
  try { claim = await createReferralClaim(env, click.clickId, click.expiresAt); }
  catch { return new Response("Referral service unavailable", { status: 503, headers: { "Cache-Control": "no-store" } }); }
  const destination = new URL(env.PLAY_STORE_URL || "https://play.google.com/store/apps/details?id=de.classydl.app");
  destination.searchParams.set("referrer", claim);
  return Response.redirect(destination.toString(), 302);
}
