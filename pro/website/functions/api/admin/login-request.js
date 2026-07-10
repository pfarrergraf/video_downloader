import {
  affiliateProgramEnabled,
  issueAdminToken,
  jsonResponse,
  normalizeEmail,
  publicBaseUrl,
  sendTransactionalEmail,
  verifyTurnstile,
} from "../../_affiliate.js";

export async function onRequestPost({ request, env }) {
  try {
    if (!affiliateProgramEnabled(env) || !env.DB) return jsonResponse({ ok: true });
    const body = await request.json().catch(() => ({}));
    if (!(await verifyTurnstile(body.turnstile_token, request, env))) {
      return jsonResponse({ error: "human_verification_failed" }, 400);
    }
    const email = normalizeEmail(body.email);
    if (!email || email !== normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)) {
      return jsonResponse({ ok: true });
    }
    const token = await issueAdminToken(env, email);
    const loginUrl = `${publicBaseUrl(request, env)}/api/admin/login?token=${encodeURIComponent(token)}`;
    await sendTransactionalEmail(env, {
      to: email,
      subject: "DownloadThat Partnerprogramm: Admin-Anmeldung",
      text: `Einmaliger Admin-Anmeldelink: ${loginUrl}`,
      html: `<p><a href="${loginUrl}">Partnerprogramm-Administration öffnen</a></p><p>Der Link ist 20 Minuten gültig.</p>`,
    });
    return jsonResponse({ ok: true });
  } catch (error) {
    console.error("admin login request failed", error);
    return jsonResponse({ ok: true });
  }
}
