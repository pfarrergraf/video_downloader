import {
  PARTNER_TERMS_VERSION,
  affiliateProgramEnabled,
  issuePartnerToken,
  isReservedPartnerCode,
  jsonResponse,
  normalizeEmail,
  normalizePartnerCode,
  normalizeSlug,
  publicBaseUrl,
  sendTransactionalEmail,
  verifyTurnstile,
  nowSeconds,
} from "../../_affiliate.js";

function validEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 254;
}

export async function onRequestPost({ request, env }) {
  try {
    if (!affiliateProgramEnabled(env) || !env.DB) return jsonResponse({ error: "not_found" }, 404);
    const body = await request.json().catch(() => ({}));
    if (!(await verifyTurnstile(body.turnstile_token, request, env))) {
      return jsonResponse({ error: "human_verification_failed" }, 400);
    }

    const email = normalizeEmail(body.email);
    const displayName = String(body.display_name || "").trim().slice(0, 100);
    const legalName = String(body.legal_name || "").trim().slice(0, 160);
    const country = String(body.country || "").trim().toUpperCase().slice(0, 2);
    const website = String(body.website || "").trim().slice(0, 500) || null;
    const code = normalizePartnerCode(body.code || displayName);
    const slug = normalizeSlug(body.slug || code || displayName);
    const channels = Array.isArray(body.channels)
      ? body.channels.map((value) => String(value).trim().slice(0, 500)).filter(Boolean).slice(0, 20)
      : [];

    if (!validEmail(email) || !displayName || !legalName || country.length !== 2) {
      return jsonResponse({ error: "invalid_fields" }, 400);
    }
    if (!body.is_adult || !body.accept_terms) {
      return jsonResponse({ error: "consent_required" }, 400);
    }
    if (code.length < 3 || slug.length < 3 || isReservedPartnerCode(code)) {
      return jsonResponse({ error: "invalid_partner_code" }, 400);
    }

    const existing = await env.DB.prepare(
      `SELECT id, status FROM affiliates
        WHERE email = ? COLLATE NOCASE OR code = ? COLLATE NOCASE OR slug = ? COLLATE NOCASE
        LIMIT 1`,
    ).bind(email, code, slug).first();
    if (existing) return jsonResponse({ error: "partner_already_exists" }, 409);

    const now = nowSeconds();
    const affiliateId = crypto.randomUUID();
    await env.DB.prepare(
      `INSERT INTO affiliates
        (id, slug, code, display_name, legal_name, email, country, website,
         channels_json, status, terms_version, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_email', ?, ?, ?)`,
    ).bind(
      affiliateId,
      slug,
      code,
      displayName,
      legalName,
      email,
      country,
      website,
      JSON.stringify(channels),
      PARTNER_TERMS_VERSION,
      now,
      now,
    ).run();

    const token = await issuePartnerToken(env, affiliateId, "verify_email");
    const verifyUrl = `${publicBaseUrl(request, env)}/api/partner/verify?token=${encodeURIComponent(token)}`;
    const mailResult = await sendTransactionalEmail(env, {
      to: email,
      subject: "DownloadThat Partnerprogramm: E-Mail bestätigen",
      text: `Bestätige deine E-Mail-Adresse für das DownloadThat Partnerprogramm: ${verifyUrl}`,
      html: `<p>Bestätige deine E-Mail-Adresse für das DownloadThat Partnerprogramm:</p><p><a href="${verifyUrl}">E-Mail bestätigen</a></p><p>Der Link ist 20 Minuten gültig.</p>`,
    });

    const response = { created: true, verification_sent: true };
    if (mailResult.development) response.development_verify_url = verifyUrl;
    return jsonResponse(response, 201);
  } catch (error) {
    console.error("partner registration failed", error);
    return jsonResponse({ error: "registration_failed", message: String(error?.message || error) }, 500);
  }
}
