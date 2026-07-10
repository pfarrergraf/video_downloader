import {
  ATTRIBUTION_SECONDS,
  affiliateProgramEnabled,
  recordAffiliateClick,
  secureCookie,
} from "../_affiliate.js";

export async function onRequestGet({ request, env, params }) {
  if (!affiliateProgramEnabled(env) || !env.DB) return new Response("Not found", { status: 404 });
  const slug = String(params.slug || "").toLowerCase();
  const affiliate = await env.DB.prepare(
    `SELECT id, slug FROM affiliates WHERE slug = ? COLLATE NOCASE AND status = 'active'`,
  ).bind(slug).first();
  if (!affiliate) return new Response("Partner not found", { status: 404 });

  const url = new URL(request.url);
  const clickId = await recordAffiliateClick(request, env, affiliate, url.searchParams.get("campaign"));
  const destination = new URL("/", url.origin);
  if (url.searchParams.get("buy") === "1") destination.searchParams.set("buy", "1");
  destination.hash = "pricing";
  return Response.redirect(destination.toString(), 302, {
    "Set-Cookie": secureCookie("dt_affiliate_click", clickId, ATTRIBUTION_SECONDS),
    "Cache-Control": "no-store",
  });
}
