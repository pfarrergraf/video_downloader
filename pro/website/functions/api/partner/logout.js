import { jsonResponse, parseCookies, sha256Hex } from "../../_affiliate.js";

export async function onRequestPost({ request, env }) {
  const token = parseCookies(request).dt_partner_session;
  if (token && env.DB) {
    await env.DB.prepare(`DELETE FROM affiliate_sessions WHERE session_hash = ?`)
      .bind(await sha256Hex(token))
      .run();
  }
  return jsonResponse({ logged_out: true }, 200, {
    "Set-Cookie": "dt_partner_session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax",
  });
}
