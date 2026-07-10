import {
  affiliateProgramEnabled,
  consumePartnerToken,
  createAffiliateSession,
  nowSeconds,
  secureCookie,
} from "../../_affiliate.js";

export async function onRequestGet({ request, env }) {
  if (!affiliateProgramEnabled(env) || !env.DB) return new Response("Not found", { status: 404 });
  const token = new URL(request.url).searchParams.get("token") || "";
  const row = await consumePartnerToken(env, token, "verify_email");
  if (!row) return new Response("Der Bestätigungslink ist ungültig oder abgelaufen.", { status: 400 });

  const now = nowSeconds();
  await env.DB.prepare(
    `UPDATE affiliates
        SET status = 'active', email_verified_at = COALESCE(email_verified_at, ?), updated_at = ?, version = version + 1
      WHERE id = ? AND status = 'pending_email'`,
  ).bind(now, now, row.affiliate_id).run();

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
