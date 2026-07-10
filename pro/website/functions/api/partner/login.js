import {
  affiliateProgramEnabled,
  consumePartnerToken,
  createAffiliateSession,
  secureCookie,
} from "../../_affiliate.js";

export async function onRequestGet({ request, env }) {
  if (!affiliateProgramEnabled(env) || !env.DB) return new Response("Not found", { status: 404 });
  const token = new URL(request.url).searchParams.get("token") || "";
  const row = await consumePartnerToken(env, token, "login");
  if (!row || row.status !== "active") {
    return new Response("Der Anmeldelink ist ungültig oder abgelaufen.", { status: 400 });
  }
  const session = await createAffiliateSession(env, row.affiliate_id, "partner");
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/partner-dashboard.html",
      "Set-Cookie": secureCookie("dt_partner_session", session, 30 * 24 * 60 * 60),
      "Cache-Control": "no-store",
    },
  });
}
