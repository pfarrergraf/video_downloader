import {
  affiliateProgramEnabled,
  consumeAdminToken,
  createAffiliateSession,
  normalizeEmail,
  secureCookie,
} from "../../_affiliate.js";

export async function onRequestGet({ request, env }) {
  if (!affiliateProgramEnabled(env) || !env.DB) return new Response("Not found", { status: 404 });
  const token = new URL(request.url).searchParams.get("token") || "";
  const row = await consumeAdminToken(env, token);
  if (!row || normalizeEmail(row.email) !== normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)) {
    return new Response("Der Admin-Anmeldelink ist ungültig oder abgelaufen.", { status: 400 });
  }
  const session = await createAffiliateSession(env, null, "admin");
  return new Response(null, {
    status: 302,
    headers: {
      Location: "/partner-admin.html",
      "Set-Cookie": secureCookie("dt_partner_session", session, 30 * 24 * 60 * 60),
      "Cache-Control": "no-store",
    },
  });
}
