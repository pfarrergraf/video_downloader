import { jsonResponse, sha256Hex } from "./_lib.js";

const DAY = 24 * 60 * 60;
const CLICK_WINDOW = 30 * DAY;
const CLAIM_PREFIX = "dt_v1=";

function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function bytes(value) {
  return new TextEncoder().encode(value);
}

async function hmacBase64Url(secret, value) {
  const key = await crypto.subtle.importKey(
    "raw",
    bytes(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return base64Url(new Uint8Array(await crypto.subtle.sign("HMAC", key, bytes(value))));
}

function safeEqual(left, right) {
  if (typeof left !== "string" || typeof right !== "string" || left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) diff |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return diff === 0;
}

function decodeBase64Url(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  return atob(normalized);
}

export function affiliateFlags(env) {
  return {
    enabled: env.AFFILIATE_ENABLED === "true",
    redirect: env.AFFILIATE_REDIRECT_ENABLED === "true",
    attribution: env.AFFILIATE_ATTRIBUTION_ENABLED === "true",
    commission: env.AFFILIATE_COMMISSION_ENABLED === "true",
    dashboard: env.AFFILIATE_DASHBOARD_ENABLED === "true",
    admin: env.AFFILIATE_ADMIN_ENABLED === "true",
  };
}

export function normalizeAffiliateCode(value) {
  const code = typeof value === "string" ? value.trim().toLowerCase() : "";
  return /^[a-z0-9](?:[a-z0-9_-]{1,62})$/.test(code) ? code : null;
}

export function normalizeCampaignSlug(value) {
  if (value == null || value === "") return null;
  const slug = typeof value === "string" ? value.trim().toLowerCase() : "";
  return /^[a-z0-9](?:[a-z0-9_-]{0,62})$/.test(slug) ? slug : null;
}

function nowSeconds(env) {
  const configured = Number(env.AFFILIATE_NOW_SECONDS);
  return Number.isInteger(configured) && configured > 0 ? configured : Math.floor(Date.now() / 1000);
}

async function audit(env, eventType, objectType, objectId, reason = null, actorType = "system") {
  if (!env.DB) return;
  await env.DB.prepare(
    `INSERT INTO affiliate_audit_events
      (id, event_type, object_type, object_id, actor_type, reason, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).bind(crypto.randomUUID(), eventType, objectType, objectId, actorType, reason, nowSeconds(env)).run();
}

export async function createReferralClaim(env, clickId, expiresAt) {
  if (!env.AFFILIATE_SIGNING_SECRET) throw new Error("affiliate signing secret is not configured");
  const payload = JSON.stringify({ v: 1, click_id: clickId, exp: expiresAt });
  const encoded = base64Url(bytes(payload));
  return `${CLAIM_PREFIX}${encoded}.${await hmacBase64Url(env.AFFILIATE_SIGNING_SECRET, encoded)}`;
}

export async function verifyReferralClaim(env, referrer, now = nowSeconds(env)) {
  if (!env.AFFILIATE_SIGNING_SECRET || typeof referrer !== "string" || !referrer.startsWith(CLAIM_PREFIX)) return null;
  const value = referrer.slice(CLAIM_PREFIX.length);
  const [encoded, suppliedMac, ...extra] = value.split(".");
  if (!encoded || !suppliedMac || extra.length || !safeEqual(suppliedMac, await hmacBase64Url(env.AFFILIATE_SIGNING_SECRET, encoded))) return null;
  let payload;
  try { payload = JSON.parse(decodeBase64Url(encoded)); } catch { return null; }
  if (payload?.v !== 1 || typeof payload.click_id !== "string" || !/^[0-9a-f-]{36}$/.test(payload.click_id)) return null;
  if (!Number.isInteger(payload.exp) || payload.exp < now) return null;
  return { clickId: payload.click_id, expiresAt: payload.exp, version: "v1" };
}

export async function hashInstallId(env, installId) {
  if (!env.AFFILIATE_INSTALL_HASH_SALT || typeof installId !== "string") return null;
  return sha256Hex(`${env.AFFILIATE_INSTALL_HASH_SALT}:${installId}`);
}

export async function recordReferralClick(env, affiliateCode, campaignSlug = null) {
  if (!env.AFFILIATE_SIGNING_SECRET) return null;
  const code = normalizeAffiliateCode(affiliateCode);
  const slug = normalizeCampaignSlug(campaignSlug);
  if (!code || campaignSlug != null && !slug) return null;
  const affiliate = await env.DB.prepare(
    `SELECT id, code FROM affiliates WHERE code = ? AND status = 'active'`,
  ).bind(code).first();
  if (!affiliate) return null;
  let campaign = null;
  if (slug) {
    campaign = await env.DB.prepare(
      `SELECT id FROM affiliate_campaigns
       WHERE affiliate_id = ? AND slug = ? AND status = 'active'`,
    ).bind(affiliate.id, slug).first();
    if (!campaign) return null;
  }
  const createdAt = nowSeconds(env);
  const clickId = crypto.randomUUID();
  const expiresAt = createdAt + CLICK_WINDOW;
  await env.DB.prepare(
    `INSERT INTO referral_clicks
      (click_id, affiliate_id, campaign_id, created_at, expires_at, source, rejected_reason)
     VALUES (?, ?, ?, ?, ?, ?, NULL)`,
  ).bind(clickId, affiliate.id, campaign?.id || null, createdAt, expiresAt, slug || "default").run();
  await audit(env, "affiliate.click.created", "referral_click", clickId);
  return { clickId, expiresAt, affiliateId: affiliate.id, campaignId: campaign?.id || null };
}

export async function attributeInstall(env, {
  installId,
  referrer,
  referrerClickTimestampSeconds,
  appInstallTimestampSeconds,
}) {
  const now = nowSeconds(env);
  const installHash = await hashInstallId(env, installId);
  if (!installHash) throw Object.assign(new Error("affiliate attribution is not configured"), { status: 503 });
  const claim = await verifyReferralClaim(env, referrer, now);
  if (!claim) throw Object.assign(new Error("invalid referral claim"), { status: 400 });
  const click = await env.DB.prepare(
    `SELECT click_id, affiliate_id, campaign_id, created_at, expires_at
     FROM referral_clicks WHERE click_id = ?`,
  ).bind(claim.clickId).first();
  if (!click || click.expires_at < now || now - click.created_at > CLICK_WINDOW) {
    throw Object.assign(new Error("referral click expired or missing"), { status: 400 });
  }
  const installTs = Number.isInteger(appInstallTimestampSeconds) ? appInstallTimestampSeconds : null;
  const clickTs = Number.isInteger(referrerClickTimestampSeconds) ? referrerClickTimestampSeconds : null;
  if (clickTs != null && (clickTs < click.created_at - 300 || clickTs > now + 300)) {
    throw Object.assign(new Error("referrer click timestamp is implausible"), { status: 400 });
  }
  if (installTs != null && (installTs < click.created_at - 300 || installTs > now + 300)) {
    throw Object.assign(new Error("install timestamp is implausible"), { status: 400 });
  }
  const existing = await env.DB.prepare(
    `SELECT id, affiliate_id, campaign_id, click_id, attributed_at
     FROM install_attributions WHERE install_id_hash = ?`,
  ).bind(installHash).first();
  if (existing) {
    if (existing.click_id !== click.click_id) throw Object.assign(new Error("install already attributed"), { status: 409 });
    return { ...existing, idempotent: true };
  }
  const id = crypto.randomUUID();
  try {
    await env.DB.prepare(
      `INSERT INTO install_attributions
        (id, affiliate_id, campaign_id, click_id, install_id_hash,
         referrer_received_at, click_timestamp, install_timestamp, attributed_at,
         attribution_source, attribution_version)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'play_install_referrer', ?)`,
    ).bind(id, click.affiliate_id, click.campaign_id, click.click_id, installHash, now, clickTs, installTs, now, claim.version).run();
  } catch (error) {
    const raced = await env.DB.prepare(
      `SELECT id, affiliate_id, campaign_id, click_id, install_id_hash, attributed_at
       FROM install_attributions WHERE install_id_hash = ? OR click_id = ?`,
    ).bind(installHash, click.click_id).first();
    if (raced) {
      if (raced.install_id_hash && raced.install_id_hash !== installHash) {
        throw Object.assign(new Error("referral click already attributed"), { status: 409 });
      }
      return { ...raced, idempotent: true };
    }
    throw error;
  }
  await audit(env, "affiliate.install.attributed", "install_attribution", id);
  return { id, affiliate_id: click.affiliate_id, campaign_id: click.campaign_id, click_id: click.click_id, attributed_at: now, idempotent: false };
}

export async function claimAffiliateEvent(env, { source, externalEventId, eventType, payload }) {
  if (!env.DB || !externalEventId) return { claimed: true, dedupe: false };
  const receivedAt = nowSeconds(env);
  const payloadHash = payload == null ? null : await sha256Hex(typeof payload === "string" ? payload : JSON.stringify(payload));
  try {
    await env.DB.prepare(
      `INSERT INTO affiliate_event_inbox
        (source, external_event_id, event_type, received_at, processed_at, status, payload_hash)
       VALUES (?, ?, ?, ?, NULL, 'received', ?)`,
    ).bind(source, externalEventId, eventType, receivedAt, payloadHash).run();
    return { claimed: true, dedupe: false };
  } catch (error) {
    const existing = await env.DB.prepare(
      `SELECT status FROM affiliate_event_inbox WHERE source = ? AND external_event_id = ?`,
    ).bind(source, externalEventId).first();
    if (existing?.status === "processed") return { claimed: false, dedupe: true, status: existing.status };
    if (existing) {
      await env.DB.prepare(
        `UPDATE affiliate_event_inbox SET status = 'received', received_at = ?, payload_hash = ?
         WHERE source = ? AND external_event_id = ?`,
      ).bind(receivedAt, payloadHash, source, externalEventId).run();
      return { claimed: true, dedupe: false, retry: true };
    }
    throw error;
  }
}

export async function completeAffiliateEvent(env, { source, externalEventId, status = "processed" }) {
  if (!env.DB || !externalEventId) return;
  await env.DB.prepare(
    `UPDATE affiliate_event_inbox SET status = ?, processed_at = ?
     WHERE source = ? AND external_event_id = ?`,
  ).bind(status, nowSeconds(env), source, externalEventId).run();
}

export function affiliateDisabledResponse() {
  return jsonResponse({ error: "affiliate_not_enabled" }, 404, { "Cache-Control": "no-store" });
}

export async function isAffiliateAdmin(request, env) {
  const expected = env.AFFILIATE_ADMIN_TOKEN;
  const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!expected || !supplied) return false;
  const [left, right] = await Promise.all([sha256Hex(supplied), sha256Hex(expected)]);
  return safeEqual(left, right);
}

export { audit, nowSeconds, CLICK_WINDOW };
