import { jsonResponse } from "../../_lib.js";
import { affiliateFlags, audit, attributeInstall } from "../../_affiliate.js";
import { attributeVerifiedPurchase } from "../../_affiliate_commissions.js";

export async function onRequestPost({ request, env }) {
  const flags = affiliateFlags(env);
  if (!flags.enabled || !flags.attribution) return jsonResponse({ error: "affiliate_not_enabled" }, 404);
  let body;
  try { body = await request.json(); } catch { return jsonResponse({ error: "invalid JSON" }, 400); }
  try {
    if (typeof body?.install_id !== "string" || body.install_id.length < 16 || body.install_id.length > 256) {
      throw Object.assign(new Error("invalid install id"), { status: 400 });
    }
    if (typeof body?.referrer !== "string" || body.referrer.length === 0 || body.referrer.length > 512) {
      throw Object.assign(new Error("invalid referral claim"), { status: 400 });
    }
    const result = await attributeInstall(env, {
      installId: body.install_id,
      referrer: body.referrer,
      referrerClickTimestampSeconds: Number.isInteger(body.referrer_click_timestamp_seconds) ? body.referrer_click_timestamp_seconds : null,
      appInstallTimestampSeconds: Number.isInteger(body.app_install_timestamp_seconds) ? body.app_install_timestamp_seconds : null,
    });
    if (flags.commission) await attributeVerifiedPurchase(env, { deviceId: body.install_id });
    return jsonResponse({ ok: true, attribution: result });
  } catch (error) {
    const status = Number(error?.status) || 500;
    await audit(env, "affiliate.attribution.rejected", "install_attribution_attempt", crypto.randomUUID(),
      status >= 500 ? "temporary backend failure" : status === 409 ? "duplicate attribution" : "invalid attribution claim", "system");
    return jsonResponse({ error: status >= 500 ? "attribution_unavailable" : error.message }, status);
  }
}
