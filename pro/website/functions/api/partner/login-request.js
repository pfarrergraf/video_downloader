import {
  affiliateProgramEnabled,
  issuePartnerToken,
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
    const affiliate = await env.DB.prepare(
      `SELECT id, email FROM affiliates WHERE email = ? COLLATE NOCASE AND status = 'active'`,
    ).bind(email).first();
    // Generic response prevents account enumeration.
    if (!affiliate) return jsonResponse({ ok: true });

    const token = await issuePartnerToken(env, affiliate.id, "login");
    const loginUrl = `${publicBaseUrl(request, env)}/api/partner/login?token=${encodeURIComponent(token)}`;
    await sendTransactionalEmail(env, {
      to: affiliate.email,
      subject: "DownloadThat Partner-Dashboard anmelden",
      text: `Öffne diesen einmaligen Anmeldelink: ${loginUrl}`,
      html: `<p><a href="${loginUrl}">Im DownloadThat Partner-Dashboard anmelden</a></p><p>Der Link ist 20 Minuten gültig.</p>`,
    });
    return jsonResponse({ ok: true });
  } catch (error) {
    console.error("partner login request failed", error);
    return jsonResponse({ ok: true });
  }
}
