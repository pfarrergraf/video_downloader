import {
  PARTNER_TERMS_VERSION,
  checkAffiliateRateLimit,
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
import { affiliateRegistrationReady } from "../../_affiliate_flags.js";

function validEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 254;
}

// Bounds registration spam / reserved-code and taken-slug enumeration from a
// single IP; Turnstile alone doesn't rate-limit a slow or CAPTCHA-farmed actor.
const RATE_LIMIT_WINDOW_SECONDS = 60 * 60;
const RATE_LIMIT_MAX_ATTEMPTS = 10;

export async function onRequestPost({ request, env }) {
  let affiliateId = null;
  try {
    if (!affiliateRegistrationReady(env)) return jsonResponse({ error: "registration_not_ready" }, 503);
    const body = await request.json().catch(() => ({}));
    if (!(await verifyTurnstile(body.turnstile_token, request, env))) {
      return jsonResponse({ error: "human_verification_failed" }, 400);
    }
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const allowed = await checkAffiliateRateLimit(
      env,
      "partner_register",
      ip,
      RATE_LIMIT_WINDOW_SECONDS,
      RATE_LIMIT_MAX_ATTEMPTS,
    );
    if (!allowed) return jsonResponse({ error: "rate_limited" }, 429);

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
    affiliateId = crypto.randomUUID();
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
    await sendTransactionalEmail(env, {
      to: email,
      subject: "DownloadThat Partnerprogramm: E-Mail bestätigen",
      text: `Bestätige deine E-Mail-Adresse für das DownloadThat Partnerprogramm: ${verifyUrl}`,
      html: `<p>Bestätige deine E-Mail-Adresse für das DownloadThat Partnerprogramm:</p><p><a href="${verifyUrl}">E-Mail bestätigen</a></p><p>Der Link ist 20 Minuten gültig.</p>`,
    });

    return jsonResponse({ created: true, verification_sent: true }, 201);
  } catch (error) {
    console.error("partner registration failed", error);
    if (affiliateId && env.DB) {
      try {
        await env.DB.batch([
          env.DB.prepare(`DELETE FROM affiliate_auth_tokens WHERE affiliate_id = ?`).bind(affiliateId),
          env.DB.prepare(`DELETE FROM affiliates WHERE id = ? AND status = 'pending_email'`).bind(affiliateId),
        ]);
      } catch (cleanupError) {
        console.error("partner registration cleanup failed", cleanupError);
      }
    }
    return jsonResponse({ error: "registration_failed" }, 500);
  }
}
