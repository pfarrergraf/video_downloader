import {
  ATTRIBUTION_SECONDS,
  affiliateProgramEnabled,
  recordAffiliateClick,
  secureCookie,
} from "../_affiliate.js";

export async function onRequestGet({ request, env, params }) {
  if (!affiliateProgramEnabled(env) || !env.DB) return new Response("Not found", { status: 404 });
  const affiliate = await env.DB.prepare(
    `SELECT id, slug FROM affiliates WHERE slug = ? COLLATE NOCASE AND status = 'active'`,
  ).bind(String(params.slug || "")).first();
  if (!affiliate) return new Response("Partner not found", { status: 404 });

  const clickId = await recordAffiliateClick(request, env, affiliate, "android-claim");
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/download?ref_claimed=1",
      "Set-Cookie": secureCookie("dt_affiliate_click", clickId, ATTRIBUTION_SECONDS),
      "Cache-Control": "no-store",
    },
  });
}
