const DAY = 24 * 60 * 60;
export const ATTRIBUTION_SECONDS = 180 * DAY;
export const COMMISSION_REVIEW_SECONDS = 30 * DAY;
export const PARTNER_SESSION_SECONDS = 30 * DAY;
export const MAGIC_LINK_SECONDS = 20 * 60;
export const PAYOUT_MINIMUM_CENTS = 5000;
export const RECONCILIATION_BLOCK_BPS = 500; // 5.00%
export const WITHDRAWAL_TEXT_VERSION = "2026-07-affiliate-v1";
export const PARTNER_TERMS_VERSION = "2026-07-v1";

const ALLOWED_COMMISSION_CENTS = new Set([200, 250, 300, 350, 400]);
const STRIPE_API = "https://api.stripe.com/v1";

export function nowSeconds() {
  return Math.floor(Date.now() / 1000);
}

export function affiliateProgramEnabled(env) {
  return String(env.AFFILIATE_PROGRAM_ENABLED || "").toLowerCase() === "true";
}

export function commissionForSaleNumber(saleNumber) {
  if (!Number.isInteger(saleNumber) || saleNumber < 1) {
    throw new RangeError("saleNumber must be a positive integer");
  }
  if (saleNumber <= 10) return 200;
  if (saleNumber <= 50) return 250;
  if (saleNumber <= 100) return 300;
  if (saleNumber <= 500) return 350;
  return 400;
}

export function expectedCommissionForCount(count) {
  if (!Number.isInteger(count) || count < 0) throw new RangeError("count must be non-negative");
  let remaining = count;
  let total = 0;
  const tiers = [
    [10, 200],
    [40, 250],
    [50, 300],
    [400, 350],
  ];
  for (const [size, cents] of tiers) {
    const used = Math.min(remaining, size);
    total += used * cents;
    remaining -= used;
    if (remaining === 0) return total;
  }
  return total + remaining * 400;
}

export function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

export function normalizePartnerCode(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9_-]/g, "")
    .slice(0, 32);
}

export function normalizeSlug(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

export function isReservedPartnerCode(value) {
  const code = normalizePartnerCode(value);
  return new Set([
    "ADMIN",
    "API",
    "APP",
    "DOWNLOADTHAT",
    "DOWNLOAD",
    "GAISTREICH",
    "STRIPE",
    "SUPPORT",
    "PARTNER",
    "AFFILIATE",
    "CREATOR",
    "NULL",
    "UNDEFINED",
  ]).has(code);
}

export function randomToken(bytes = 24) {
  const data = crypto.getRandomValues(new Uint8Array(bytes));
  return [...data].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(value)));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

async function objectHash(value) {
  return sha256Hex(JSON.stringify(canonicalize(value)));
}

export function jsonResponse(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function parseCookies(request) {
  const raw = request.headers.get("Cookie") || "";
  const result = {};
  for (const part of raw.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (!name) continue;
    result[name] = decodeURIComponent(rest.join("="));
  }
  return result;
}

export function secureCookie(name, value, maxAge, path = "/") {
  return `${name}=${encodeURIComponent(value)}; Path=${path}; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;
}

export function publicBaseUrl(request, env) {
  if (env.PUBLIC_BASE_URL) return String(env.PUBLIC_BASE_URL).replace(/\/$/, "");
  return new URL(request.url).origin;
}

async function stripeRequest(path, env, options = {}) {
  if (!env.STRIPE_SECRET_KEY) throw new Error("STRIPE_SECRET_KEY is not configured");
  const response = await fetch(`${STRIPE_API}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(`Stripe ${options.method || "GET"} ${path} failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

async function stripePost(path, env, body) {
  return stripeRequest(path, env, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
  });
}

export async function verifyTurnstile(token, request, env) {
  if (!env.TURNSTILE_SECRET_KEY) {
    if (String(env.ENVIRONMENT || "production") === "production") return false;
    return true;
  }
  if (!token) return false;
  const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      secret: env.TURNSTILE_SECRET_KEY,
      response: token,
      remoteip: request.headers.get("CF-Connecting-IP") || "",
    }),
  });
  if (!response.ok) return false;
  const result = await response.json();
  return result.success === true;
}

export async function sendTransactionalEmail(env, { to, subject, html, text }) {
  if (!env.RESEND_API_KEY || !env.PARTNER_FROM_EMAIL) {
    if (String(env.ENVIRONMENT || "production") === "production") {
      throw new Error("Transactional email is not configured");
    }
    console.log("Development email", { to, subject, text });
    return { development: true };
  }
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: env.PARTNER_FROM_EMAIL,
      to: [to],
      subject,
      html,
      text,
    }),
  });
  if (!response.ok) throw new Error(`Resend failed: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function issuePartnerToken(env, affiliateId, purpose) {
  const token = randomToken(32);
  const tokenHash = await sha256Hex(token);
  const now = nowSeconds();
  await env.DB.prepare(
    `INSERT INTO affiliate_auth_tokens
      (id, affiliate_id, token_hash, purpose, expires_at, created_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  )
    .bind(crypto.randomUUID(), affiliateId, tokenHash, purpose, now + MAGIC_LINK_SECONDS, now)
    .run();
  return token;
}

export async function issueAdminToken(env, email) {
  const token = randomToken(32);
  const tokenHash = await sha256Hex(token);
  const now = nowSeconds();
  await env.DB.prepare(
    `INSERT INTO affiliate_admin_tokens
      (id, email, token_hash, expires_at, created_at)
     VALUES (?, ?, ?, ?, ?)`,
  )
    .bind(crypto.randomUUID(), normalizeEmail(email), tokenHash, now + MAGIC_LINK_SECONDS, now)
    .run();
  return token;
}

export async function consumePartnerToken(env, token, purpose) {
  const tokenHash = await sha256Hex(token);
  const now = nowSeconds();
  const row = await env.DB.prepare(
    `SELECT t.*, a.email, a.status
       FROM affiliate_auth_tokens t
       JOIN affiliates a ON a.id = t.affiliate_id
      WHERE t.token_hash = ? AND t.purpose = ? AND t.used_at IS NULL AND t.expires_at >= ?`,
  )
    .bind(tokenHash, purpose, now)
    .first();
  if (!row) return null;
  await env.DB.prepare(`UPDATE affiliate_auth_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL`)
    .bind(now, row.id)
    .run();
  return row;
}

export async function consumeAdminToken(env, token) {
  const tokenHash = await sha256Hex(token);
  const now = nowSeconds();
  const row = await env.DB.prepare(
    `SELECT * FROM affiliate_admin_tokens
      WHERE token_hash = ? AND used_at IS NULL AND expires_at >= ?`,
  )
    .bind(tokenHash, now)
    .first();
  if (!row) return null;
  await env.DB.prepare(`UPDATE affiliate_admin_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL`)
    .bind(now, row.id)
    .run();
  return row;
}

export async function createAffiliateSession(env, affiliateId, role) {
  const token = randomToken(32);
  const sessionHash = await sha256Hex(token);
  const now = nowSeconds();
  await env.DB.prepare(
    `INSERT INTO affiliate_sessions
      (session_hash, affiliate_id, role, expires_at, created_at, last_seen_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  )
    .bind(sessionHash, affiliateId || null, role, now + PARTNER_SESSION_SECONDS, now, now)
    .run();
  return token;
}

export async function getAffiliateSession(request, env, requiredRole = null) {
  const token = parseCookies(request).dt_partner_session;
  if (!token) return null;
  const sessionHash = await sha256Hex(token);
  const now = nowSeconds();
  const row = await env.DB.prepare(
    `SELECT s.*, a.email, a.display_name, a.status AS affiliate_status
       FROM affiliate_sessions s
       LEFT JOIN affiliates a ON a.id = s.affiliate_id
      WHERE s.session_hash = ? AND s.expires_at >= ?`,
  )
    .bind(sessionHash, now)
    .first();
  if (!row || (requiredRole && row.role !== requiredRole)) return null;
  await env.DB.prepare(`UPDATE affiliate_sessions SET last_seen_at = ? WHERE session_hash = ?`)
    .bind(now, sessionHash)
    .run();
  return row;
}

async function appendChainedRow(env, table, values, actorField) {
  const previous = await env.DB.prepare(`SELECT entry_hash FROM ${table} ORDER BY created_at DESC, id DESC LIMIT 1`).first();
  const previousHash = previous?.entry_hash || null;
  const createdAt = nowSeconds();
  const id = crypto.randomUUID();
  const payload = { id, ...values, previous_hash: previousHash, created_at: createdAt };
  const entryHash = await objectHash(payload);
  if (table === "affiliate_audit_log") {
    await env.DB.prepare(
      `INSERT INTO affiliate_audit_log
        (id, actor, action, entity_type, entity_id, details_json, previous_hash, entry_hash, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
      .bind(
        id,
        values.actor,
        values.action,
        values.entity_type,
        values.entity_id,
        values.details_json,
        previousHash,
        entryHash,
        createdAt,
      )
      .run();
  } else {
    await env.DB.prepare(
      `INSERT INTO affiliate_ledger
        (id, affiliate_id, entry_type, amount_cents, reference_type, reference_id,
         created_by, previous_hash, entry_hash, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
      .bind(
        id,
        values.affiliate_id,
        values.entry_type,
        values.amount_cents,
        values.reference_type,
        values.reference_id,
        values[actorField],
        previousHash,
        entryHash,
        createdAt,
      )
      .run();
  }
  return { id, entryHash, createdAt };
}

export async function appendAudit(env, actor, action, entityType, entityId, details = {}) {
  return appendChainedRow(
    env,
    "affiliate_audit_log",
    {
      actor,
      action,
      entity_type: entityType,
      entity_id: entityId,
      details_json: JSON.stringify(details),
    },
    "actor",
  );
}

export async function appendLedger(env, affiliateId, entryType, amountCents, referenceType, referenceId, createdBy) {
  if (!Number.isInteger(amountCents) || amountCents === 0) throw new Error("Ledger amount must be a non-zero integer");
  return appendChainedRow(
    env,
    "affiliate_ledger",
    {
      affiliate_id: affiliateId,
      entry_type: entryType,
      amount_cents: amountCents,
      reference_type: referenceType,
      reference_id: referenceId,
      created_by: createdBy,
    },
    "created_by",
  );
}

export async function recordAffiliateClick(request, env, affiliate, campaign = null) {
  const now = nowSeconds();
  const clickId = crypto.randomUUID();
  const ip = request.headers.get("CF-Connecting-IP") || "";
  const userAgent = request.headers.get("User-Agent") || "";
  await env.DB.prepare(
    `INSERT INTO affiliate_clicks
      (id, affiliate_id, campaign, landing_path, ip_hash, user_agent_hash, created_at, expires_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  )
    .bind(
      clickId,
      affiliate.id,
      campaign ? String(campaign).slice(0, 80) : null,
      new URL(request.url).pathname,
      ip ? await sha256Hex(`${env.REFERRAL_HASH_SALT || ""}:${ip}`) : null,
      userAgent ? await sha256Hex(`${env.REFERRAL_HASH_SALT || ""}:${userAgent}`) : null,
      now,
      now + ATTRIBUTION_SECONDS,
    )
    .run();
  return clickId;
}

export async function resolveAffiliateAttribution(request, env, explicitCode = "") {
  const now = nowSeconds();
  const code = normalizePartnerCode(explicitCode);
  if (code) {
    const affiliate = await env.DB.prepare(
      `SELECT * FROM affiliates WHERE code = ? COLLATE NOCASE AND status = 'active'`,
    )
      .bind(code)
      .first();
    if (!affiliate) return { error: "invalid_partner_code" };
    return { affiliate, click: null, source: "code" };
  }

  const clickId = parseCookies(request).dt_affiliate_click;
  if (!clickId) return { affiliate: null, click: null, source: "none" };
  const click = await env.DB.prepare(
    `SELECT c.*, a.status AS affiliate_status, a.email AS affiliate_email,
            a.display_name, a.code, a.slug
       FROM affiliate_clicks c
       JOIN affiliates a ON a.id = c.affiliate_id
      WHERE c.id = ? AND c.expires_at >= ? AND a.status = 'active'`,
  )
    .bind(clickId, now)
    .first();
  if (!click) return { affiliate: null, click: null, source: "expired" };
  return {
    affiliate: {
      id: click.affiliate_id,
      email: click.affiliate_email,
      display_name: click.display_name,
      code: click.code,
      slug: click.slug,
    },
    click,
    source: "cookie",
  };
}

export async function createDynamicCheckout(request, env, body) {
  if (!env.STRIPE_PRICE_ID) throw new Error("STRIPE_PRICE_ID is not configured");
  const withdrawalChoice = body.withdrawal_choice === "wait14" ? "wait14" : "waived";
  const attribution = await resolveAffiliateAttribution(request, env, body.partner_code || "");
  if (attribution.error) return { error: attribution.error, status: 400 };

  const now = nowSeconds();
  const intentId = crypto.randomUUID();
  const base = publicBaseUrl(request, env);
  const locale = /^[a-z]{2}(?:-[A-Z]{2})?$/.test(String(body.locale || "")) ? String(body.locale) : "auto";

  await env.DB.prepare(
    `INSERT INTO affiliate_checkout_intents
      (id, affiliate_id, click_id, withdrawal_choice, withdrawal_consented_at,
       withdrawal_text_version, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  )
    .bind(
      intentId,
      attribution.affiliate?.id || null,
      attribution.click?.id || null,
      withdrawalChoice,
      withdrawalChoice === "waived" ? now : null,
      WITHDRAWAL_TEXT_VERSION,
      now,
    )
    .run();

  const stripeBody = {
    mode: "payment",
    success_url: `${base}/success.html?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${base}/#pricing`,
    locale,
    client_reference_id: intentId,
    "line_items[0][price]": env.STRIPE_PRICE_ID,
    "line_items[0][quantity]": "1",
    "metadata[tier]": "lifetime",
    "metadata[checkout_intent_id]": intentId,
    "metadata[affiliate_id]": attribution.affiliate?.id || "",
    "metadata[withdrawal_choice]": withdrawalChoice,
    "metadata[withdrawal_text_version]": WITHDRAWAL_TEXT_VERSION,
    "payment_intent_data[metadata][checkout_intent_id]": intentId,
    "payment_intent_data[metadata][affiliate_id]": attribution.affiliate?.id || "",
  };

  const session = await stripePost("/checkout/sessions", env, stripeBody);
  await env.DB.prepare(
    `UPDATE affiliate_checkout_intents
        SET stripe_checkout_session_id = ?
      WHERE id = ? AND stripe_checkout_session_id IS NULL`,
  )
    .bind(session.id, intentId)
    .run();

  return { url: session.url, session_id: session.id };
}

export async function handleAffiliateCheckoutPaid(session, licenseKey, env) {
  const intentId = session.metadata?.checkout_intent_id || session.client_reference_id;
  if (!intentId) return { attributed: false, reason: "no checkout intent" };

  const intent = await env.DB.prepare(`SELECT * FROM affiliate_checkout_intents WHERE id = ?`)
    .bind(intentId)
    .first();
  if (!intent) return { attributed: false, reason: "checkout intent not found" };

  const now = nowSeconds();
  const paymentIntentId = typeof session.payment_intent === "string"
    ? session.payment_intent
    : session.payment_intent?.id || null;
  const amountTotal = Number.isInteger(session.amount_total) ? session.amount_total : null;
  const currency = session.currency || null;

  const statements = [
    env.DB.prepare(
      `UPDATE affiliate_checkout_intents
          SET payment_status = 'paid', amount_total_cents = ?, currency = ?, finalized_at = ?
        WHERE id = ?`,
    ).bind(amountTotal, currency, now, intentId),
    env.DB.prepare(
      `UPDATE licenses
          SET affiliate_id = ?, affiliate_click_id = ?, stripe_payment_intent_id = ?,
              amount_total_cents = ?, currency = ?, updated_at = ?
        WHERE license_key = ?`,
    ).bind(intent.affiliate_id, intent.click_id, paymentIntentId, amountTotal, currency, now, licenseKey),
  ];

  if (intent.click_id) {
    statements.push(
      env.DB.prepare(`UPDATE affiliate_clicks SET converted_at = COALESCE(converted_at, ?) WHERE id = ?`)
        .bind(now, intent.click_id),
    );
  }

  if (intent.affiliate_id) {
    const affiliate = await env.DB.prepare(`SELECT id, status FROM affiliates WHERE id = ?`)
      .bind(intent.affiliate_id)
      .first();
    if (affiliate?.status === "active") {
      const commissionId = crypto.randomUUID();
      statements.push(
        env.DB.prepare(
          `INSERT OR IGNORE INTO affiliate_commissions
            (id, affiliate_id, license_key, stripe_checkout_session_id,
             stripe_payment_intent_id, status, eligible_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)`,
        ).bind(
          commissionId,
          intent.affiliate_id,
          licenseKey,
          session.id,
          paymentIntentId,
          now + COMMISSION_REVIEW_SECONDS,
          now,
          now,
        ),
        env.DB.prepare(
          `UPDATE licenses
              SET affiliate_commission_id = COALESCE(affiliate_commission_id, ?)
            WHERE license_key = ?`,
        ).bind(commissionId, licenseKey),
      );
    }
  }

  await env.DB.batch(statements);
  return { attributed: Boolean(intent.affiliate_id), affiliate_id: intent.affiliate_id || null };
}

export async function reverseCommission(env, { sessionId = null, paymentIntentId = null, reason, actor = "stripe-webhook" }) {
  if (!sessionId && !paymentIntentId) return { reversed: false, reason: "missing identifier" };
  const commission = await env.DB.prepare(
    `SELECT * FROM affiliate_commissions
      WHERE (? IS NOT NULL AND stripe_checkout_session_id = ?)
         OR (? IS NOT NULL AND stripe_payment_intent_id = ?)
      LIMIT 1`,
  )
    .bind(sessionId, sessionId, paymentIntentId, paymentIntentId)
    .first();
  if (!commission) return { reversed: false, reason: "commission not found" };
  if (["reversed", "rejected"].includes(commission.status)) return { reversed: false, reason: "already reversed" };

  const now = nowSeconds();
  const wasSettled = Number(commission.settled_cents || 0);
  await env.DB.prepare(
    `UPDATE affiliate_commissions
        SET status = 'reversed', reversed_at = ?, reversal_reason = ?, updated_at = ?
      WHERE id = ? AND status NOT IN ('reversed', 'rejected')`,
  )
    .bind(now, reason, now, commission.id)
    .run();

  if (commission.qualified_sale_number && commission.commission_cents) {
    try {
      await appendLedger(
        env,
        commission.affiliate_id,
        "commission_reversed",
        -Number(commission.commission_cents),
        "commission",
        commission.id,
        actor,
      );
    } catch (error) {
      if (!String(error.message || error).includes("UNIQUE")) throw error;
    }
  }

  if (wasSettled > 0) {
    await env.DB.prepare(
      `UPDATE affiliates
          SET negative_balance_cents = negative_balance_cents + ?, updated_at = ?, version = version + 1
        WHERE id = ?`,
    )
      .bind(wasSettled, now, commission.affiliate_id)
      .run();
  }

  await appendAudit(env, actor, "commission_reversed", "commission", commission.id, {
    reason,
    settled_cents: wasSettled,
  });
  return { reversed: true, commission_id: commission.id, clawback_cents: wasSettled };
}

async function fetchStripeSessionReality(sessionId, env) {
  const session = await stripeRequest(
    `/checkout/sessions/${encodeURIComponent(sessionId)}?expand[]=payment_intent.latest_charge`,
    env,
  );
  const paymentIntent = session.payment_intent;
  const charge = paymentIntent && typeof paymentIntent === "object" ? paymentIntent.latest_charge : null;
  const paid = session.payment_status === "paid" && (!paymentIntent || paymentIntent.status === "succeeded");
  const amountReceived = Number(paymentIntent?.amount_received ?? session.amount_total ?? 0);
  const amountRefunded = Number(charge?.amount_refunded ?? 0);
  const disputed = Boolean(charge?.disputed);
  return {
    session,
    valid: paid && !disputed && amountReceived - amountRefunded > 0,
    netRevenueCents: Math.max(0, amountReceived - amountRefunded),
    disputed,
    refunded: amountRefunded > 0,
  };
}

export async function approveEligibleCommissions(env, actor = "reconciliation") {
  const now = nowSeconds();
  const pending = await env.DB.prepare(
    `SELECT c.*, l.status AS license_status
       FROM affiliate_commissions c
       JOIN licenses l ON l.license_key = c.license_key
      WHERE c.status = 'pending' AND c.eligible_at <= ?
      ORDER BY c.created_at ASC, c.id ASC`,
  )
    .bind(now)
    .all();

  const results = [];
  for (const commission of pending.results || []) {
    if (commission.license_status !== "active") {
      await reverseCommission(env, {
        sessionId: commission.stripe_checkout_session_id,
        reason: `license_${commission.license_status}`,
        actor,
      });
      results.push({ id: commission.id, status: "reversed" });
      continue;
    }

    let reality;
    try {
      reality = await fetchStripeSessionReality(commission.stripe_checkout_session_id, env);
    } catch (error) {
      results.push({ id: commission.id, status: "deferred", error: String(error.message || error) });
      continue;
    }
    if (!reality.valid) {
      await reverseCommission(env, {
        sessionId: commission.stripe_checkout_session_id,
        reason: reality.disputed ? "stripe_disputed" : reality.refunded ? "stripe_refunded" : "stripe_not_paid",
        actor,
      });
      results.push({ id: commission.id, status: "reversed" });
      continue;
    }

    let approved = false;
    for (let attempt = 0; attempt < 4 && !approved; attempt++) {
      const affiliate = await env.DB.prepare(
        `SELECT approved_sale_count, version FROM affiliates WHERE id = ? AND status = 'active'`,
      )
        .bind(commission.affiliate_id)
        .first();
      if (!affiliate) break;
      const oldVersion = Number(affiliate.version || 0);
      const saleNumber = Number(affiliate.approved_sale_count || 0) + 1;
      const cents = commissionForSaleNumber(saleNumber);
      const changed = await env.DB.prepare(
        `UPDATE affiliates
            SET approved_sale_count = ?, lifetime_approved_cents = lifetime_approved_cents + ?,
                updated_at = ?, version = version + 1
          WHERE id = ? AND version = ? AND status = 'active'`,
      )
        .bind(saleNumber, cents, now, commission.affiliate_id, oldVersion)
        .run();
      if ((changed.meta?.changes || 0) !== 1) continue;

      const commissionUpdate = await env.DB.prepare(
        `UPDATE affiliate_commissions
            SET status = 'approved', qualified_sale_number = ?, commission_cents = ?,
                approved_at = ?, updated_at = ?
          WHERE id = ? AND status = 'pending'`,
      )
        .bind(saleNumber, cents, now, now, commission.id)
        .run();
      if ((commissionUpdate.meta?.changes || 0) !== 1) {
        // Fail closed: an unexpected concurrent status change freezes payouts during reconciliation.
        await env.DB.prepare(
          `UPDATE affiliate_controls
              SET payout_frozen = 1, freeze_reason = ?, frozen_at = ?, updated_at = ?
            WHERE id = 'global'`,
        )
          .bind(`Commission approval race for ${commission.id}`, now, now)
          .run();
        throw new Error(`Commission approval race for ${commission.id}`);
      }

      await appendLedger(
        env,
        commission.affiliate_id,
        "commission_approved",
        cents,
        "commission",
        commission.id,
        actor,
      );
      await appendAudit(env, actor, "commission_approved", "commission", commission.id, {
        sale_number: saleNumber,
        commission_cents: cents,
      });
      approved = true;
      results.push({ id: commission.id, status: "approved", sale_number: saleNumber, cents });
    }
    if (!approved) results.push({ id: commission.id, status: "deferred_concurrency" });
  }
  return results;
}

function deviationBps(left, right) {
  const a = Number(left || 0);
  const b = Number(right || 0);
  if (a === 0 && b === 0) return 0;
  return Math.round((Math.abs(a - b) * 10000) / Math.max(Math.abs(a), Math.abs(b), 1));
}

async function fetchStripeAffiliateReality(env) {
  let startingAfter = null;
  let pages = 0;
  let paidEverCount = 0;
  let validCount = 0;
  let validRevenueCents = 0;
  const sessionIds = new Set();

  while (pages < 100) {
    const params = new URLSearchParams({ limit: "100" });
    params.append("expand[]", "data.payment_intent.latest_charge");
    if (startingAfter) params.set("starting_after", startingAfter);
    const page = await stripeRequest(`/checkout/sessions?${params}`, env);
    pages += 1;
    for (const session of page.data || []) {
      if (!session.metadata?.checkout_intent_id && !session.metadata?.affiliate_id) continue;
      if (!session.metadata?.affiliate_id) continue;
      if (session.payment_status !== "paid") continue;
      paidEverCount += 1;
      sessionIds.add(session.id);
      let paymentIntent = session.payment_intent;
      if (typeof paymentIntent === "string") {
        paymentIntent = await stripeRequest(`/payment_intents/${paymentIntent}?expand[]=latest_charge`, env);
      }
      const charge = paymentIntent?.latest_charge;
      const amountReceived = Number(paymentIntent?.amount_received ?? session.amount_total ?? 0);
      const amountRefunded = Number(charge?.amount_refunded ?? 0);
      const net = Math.max(0, amountReceived - amountRefunded);
      if (paymentIntent?.status === "succeeded" && !charge?.disputed && net > 0) {
        validCount += 1;
        validRevenueCents += net;
      }
    }
    if (!page.has_more) return { paidEverCount, validCount, validRevenueCents, sessionIds };
    const last = page.data?.[page.data.length - 1];
    if (!last?.id) throw new Error("Stripe pagination returned has_more without a cursor");
    startingAfter = last.id;
  }
  throw new Error("Stripe reconciliation exceeded 10,000 Checkout Sessions; refusing partial reconciliation");
}

async function localFinanceReality(env) {
  const licenses = await env.DB.prepare(
    `SELECT
       COUNT(*) AS all_count,
       SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS valid_count,
       COALESCE(SUM(CASE WHEN status = 'active' THEN amount_total_cents ELSE 0 END), 0) AS valid_revenue_cents
     FROM licenses
     WHERE affiliate_id IS NOT NULL`,
  ).first();

  const commissions = await env.DB.prepare(
    `SELECT
       COUNT(*) AS total_count,
       COALESCE(SUM(CASE WHEN qualified_sale_number IS NOT NULL THEN commission_cents ELSE 0 END), 0) AS recorded_original_cents,
       COALESCE(SUM(CASE
         WHEN status IN ('approved', 'paid') THEN MAX(commission_cents - settled_cents, 0)
         ELSE 0 END), 0) AS outstanding_commission_cents,
       COALESCE(SUM(CASE
         WHEN status IN ('approved', 'paid') THEN commission_cents
         ELSE 0 END), 0) AS net_earned_cents
     FROM affiliate_commissions`,
  ).first();

  const expected = await env.DB.prepare(
    `SELECT COALESCE(SUM(CASE
       WHEN qualified_sale_number BETWEEN 1 AND 10 THEN 200
       WHEN qualified_sale_number BETWEEN 11 AND 50 THEN 250
       WHEN qualified_sale_number BETWEEN 51 AND 100 THEN 300
       WHEN qualified_sale_number BETWEEN 101 AND 500 THEN 350
       WHEN qualified_sale_number >= 501 THEN 400
       ELSE 0 END), 0) AS expected_cents
     FROM affiliate_commissions`,
  ).first();

  const ledger = await env.DB.prepare(
    `SELECT COALESCE(SUM(amount_cents), 0) AS balance_cents FROM affiliate_ledger`,
  ).first();

  const payouts = await env.DB.prepare(
    `SELECT COALESCE(SUM(CASE WHEN status = 'paid' THEN amount_cents ELSE 0 END), 0) AS paid_cents
     FROM affiliate_payouts`,
  ).first();

  const negative = await env.DB.prepare(
    `SELECT COALESCE(SUM(negative_balance_cents), 0) AS negative_cents FROM affiliates`,
  ).first();

  const allocationProblems = await env.DB.prepare(
    `SELECT COUNT(*) AS count FROM (
       SELECT c.id
         FROM affiliate_commissions c
         LEFT JOIN affiliate_payout_allocations a ON a.commission_id = c.id
        GROUP BY c.id
       HAVING COALESCE(SUM(a.amount_cents), 0) <> c.settled_cents
           OR COALESCE(SUM(a.amount_cents), 0) > COALESCE(c.commission_cents, 0)
     )`,
  ).first();

  const payoutProblems = await env.DB.prepare(
    `SELECT COUNT(*) AS count FROM (
       SELECT p.id
         FROM affiliate_payouts p
         LEFT JOIN affiliate_payout_allocations a ON a.payout_id = p.id
        GROUP BY p.id
       HAVING COALESCE(SUM(a.amount_cents), 0) - p.negative_balance_applied_cents <> p.amount_cents
     )`,
  ).first();

  const invalidAmounts = await env.DB.prepare(
    `SELECT COUNT(*) AS count FROM affiliate_commissions
      WHERE commission_cents IS NOT NULL AND commission_cents NOT IN (200, 250, 300, 350, 400)`,
  ).first();

  return {
    allLicenseCount: Number(licenses?.all_count || 0),
    validLicenseCount: Number(licenses?.valid_count || 0),
    validRevenueCents: Number(licenses?.valid_revenue_cents || 0),
    commissionCount: Number(commissions?.total_count || 0),
    recordedOriginalCents: Number(commissions?.recorded_original_cents || 0),
    outstandingCommissionCents: Number(commissions?.outstanding_commission_cents || 0),
    netEarnedCents: Number(commissions?.net_earned_cents || 0),
    expectedCommissionCents: Number(expected?.expected_cents || 0),
    ledgerBalanceCents: Number(ledger?.balance_cents || 0),
    paidOutCents: Number(payouts?.paid_cents || 0),
    negativeBalanceCents: Number(negative?.negative_cents || 0),
    allocationProblemCount: Number(allocationProblems?.count || 0),
    payoutProblemCount: Number(payoutProblems?.count || 0),
    invalidAmountCount: Number(invalidAmounts?.count || 0),
  };
}

async function acquireReconciliationLease(env) {
  const now = nowSeconds();
  const token = randomToken(16);
  const result = await env.DB.prepare(
    `UPDATE affiliate_controls
        SET reconciliation_lock_token = ?, reconciliation_lock_until = ?, updated_at = ?
      WHERE id = 'global'
        AND (reconciliation_lock_until IS NULL OR reconciliation_lock_until < ?)`,
  )
    .bind(token, now + 10 * 60, now, now)
    .run();
  if ((result.meta?.changes || 0) !== 1) throw new Error("A reconciliation is already running");
  return token;
}

async function releaseReconciliationLease(env, token) {
  await env.DB.prepare(
    `UPDATE affiliate_controls
        SET reconciliation_lock_token = NULL, reconciliation_lock_until = NULL, updated_at = ?
      WHERE id = 'global' AND reconciliation_lock_token = ?`,
  )
    .bind(nowSeconds(), token)
    .run();
}

export async function runReconciliation(env, actor = "system") {
  const lease = await acquireReconciliationLease(env);
  try {
    await approveEligibleCommissions(env, actor);
    const [local, stripe] = await Promise.all([
      localFinanceReality(env),
      fetchStripeAffiliateReality(env),
    ]);

    const expectedLedger = local.netEarnedCents - local.paidOutCents;
    const revenueDeviation = deviationBps(local.validRevenueCents, stripe.validRevenueCents);
    const countDeviation = deviationBps(local.validLicenseCount, stripe.validCount);
    const commissionDeviation = deviationBps(local.expectedCommissionCents, local.recordedOriginalCents);
    const ledgerDeviation = deviationBps(expectedLedger, local.ledgerBalanceCents);
    const maxPossibleCommission = stripe.paidEverCount * 400;

    const hardReasons = [];
    if (local.invalidAmountCount > 0) hardReasons.push("invalid_commission_amount");
    if (local.allocationProblemCount > 0) hardReasons.push("allocation_mismatch");
    if (local.payoutProblemCount > 0) hardReasons.push("payout_allocation_mismatch");
    if (local.paidOutCents > maxPossibleCommission) hardReasons.push("historical_payout_exceeds_absolute_license_ceiling");
    if (local.recordedOriginalCents > maxPossibleCommission) hardReasons.push("commissions_exceed_absolute_license_ceiling");
    if (local.commissionCount > stripe.paidEverCount) hardReasons.push("more_commissions_than_paid_affiliate_sessions");
    if (local.ledgerBalanceCents !== expectedLedger) hardReasons.push("ledger_balance_not_equal_to_commissions_minus_payouts");

    const deviationReasons = [];
    if (revenueDeviation > RECONCILIATION_BLOCK_BPS) deviationReasons.push("revenue_deviation_over_5_percent");
    if (countDeviation > RECONCILIATION_BLOCK_BPS) deviationReasons.push("license_count_deviation_over_5_percent");
    if (commissionDeviation > RECONCILIATION_BLOCK_BPS) deviationReasons.push("commission_schedule_deviation_over_5_percent");
    if (ledgerDeviation > RECONCILIATION_BLOCK_BPS) deviationReasons.push("ledger_deviation_over_5_percent");

    const reasons = [...hardReasons, ...deviationReasons];
    const status = hardReasons.length > 0 || deviationReasons.length > 0 ? "blocked" : "ok";
    const previous = await env.DB.prepare(
      `SELECT snapshot_hash FROM affiliate_reconciliation_snapshots
       ORDER BY created_at DESC, id DESC LIMIT 1`,
    ).first();
    const snapshotId = crypto.randomUUID();
    const createdAt = nowSeconds();
    const snapshotData = {
      id: snapshotId,
      status,
      valid_license_count: local.validLicenseCount,
      stripe_paid_session_count: stripe.validCount,
      stripe_paid_ever_count: stripe.paidEverCount,
      recognized_revenue_cents: local.validRevenueCents,
      expected_commission_cents: local.expectedCommissionCents,
      recorded_liability_cents: local.outstandingCommissionCents,
      ledger_liability_cents: local.ledgerBalanceCents,
      paid_out_cents: local.paidOutCents,
      max_possible_commission_cents: maxPossibleCommission,
      revenue_deviation_bps: revenueDeviation,
      count_deviation_bps: countDeviation,
      commission_deviation_bps: commissionDeviation,
      ledger_deviation_bps: ledgerDeviation,
      reasons_json: JSON.stringify(reasons),
      previous_hash: previous?.snapshot_hash || null,
      created_at: createdAt,
    };
    const snapshotHash = await objectHash(snapshotData);
    const freezeReason = reasons.length ? reasons.join(", ") : "";

    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO affiliate_reconciliation_snapshots
          (id, status, valid_license_count, stripe_paid_session_count,
           recognized_revenue_cents, expected_commission_cents, recorded_liability_cents,
           ledger_liability_cents, paid_out_cents, max_possible_commission_cents,
           revenue_deviation_bps, commission_deviation_bps, reasons_json,
           previous_hash, snapshot_hash, created_at, stripe_paid_ever_count,
           count_deviation_bps, ledger_deviation_bps)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).bind(
        snapshotId,
        status,
        local.validLicenseCount,
        stripe.validCount,
        local.validRevenueCents,
        local.expectedCommissionCents,
        local.outstandingCommissionCents,
        local.ledgerBalanceCents,
        local.paidOutCents,
        maxPossibleCommission,
        revenueDeviation,
        commissionDeviation,
        JSON.stringify(reasons),
        previous?.snapshot_hash || null,
        snapshotHash,
        createdAt,
        stripe.paidEverCount,
        countDeviation,
        ledgerDeviation,
      ),
      env.DB.prepare(
        `UPDATE affiliate_controls
            SET payout_frozen = ?, freeze_reason = ?, frozen_at = ?,
                last_reconciliation_at = ?, last_reconciliation_snapshot_id = ?, updated_at = ?
          WHERE id = 'global'`,
      ).bind(
        status === "blocked" ? 1 : 0,
        freezeReason,
        status === "blocked" ? createdAt : null,
        createdAt,
        snapshotId,
        createdAt,
      ),
    ]);

    await appendAudit(env, actor, "reconciliation_completed", "reconciliation", snapshotId, {
      status,
      reasons,
      local,
      stripe: {
        paidEverCount: stripe.paidEverCount,
        validCount: stripe.validCount,
        validRevenueCents: stripe.validRevenueCents,
      },
    });

    return { id: snapshotId, status, reasons, local, stripe: {
      paidEverCount: stripe.paidEverCount,
      validCount: stripe.validCount,
      validRevenueCents: stripe.validRevenueCents,
    }, deviations: {
      revenue_bps: revenueDeviation,
      count_bps: countDeviation,
      commission_bps: commissionDeviation,
      ledger_bps: ledgerDeviation,
    } };
  } catch (error) {
    const now = nowSeconds();
    await env.DB.prepare(
      `UPDATE affiliate_controls
          SET payout_frozen = 1, freeze_reason = ?, frozen_at = COALESCE(frozen_at, ?), updated_at = ?
        WHERE id = 'global'`,
    )
      .bind(`Reconciliation failed: ${String(error.message || error).slice(0, 500)}`, now, now)
      .run();
    throw error;
  } finally {
    await releaseReconciliationLease(env, lease);
  }
}

export async function prepareAffiliatePayout(env, affiliateId, actor = "system") {
  const reconciliation = await runReconciliation(env, actor);
  if (reconciliation.status !== "ok") {
    return { error: "payouts_frozen", reconciliation, status: 409 };
  }
  const controls = await env.DB.prepare(`SELECT * FROM affiliate_controls WHERE id = 'global'`).first();
  if (!controls || controls.payout_frozen) return { error: "payouts_frozen", status: 409 };

  const affiliate = await env.DB.prepare(`SELECT * FROM affiliates WHERE id = ? AND status = 'active'`)
    .bind(affiliateId)
    .first();
  if (!affiliate) return { error: "affiliate_not_active", status: 404 };

  const commissions = await env.DB.prepare(
    `SELECT * FROM affiliate_commissions
      WHERE affiliate_id = ? AND status = 'approved'
        AND commission_cents > settled_cents
      ORDER BY approved_at ASC, id ASC`,
  )
    .bind(affiliateId)
    .all();
  const grossAvailable = (commissions.results || []).reduce(
    (sum, row) => sum + Number(row.commission_cents) - Number(row.settled_cents || 0),
    0,
  );
  const negativeApplied = Math.min(grossAvailable, Number(affiliate.negative_balance_cents || 0));
  const payable = grossAvailable - negativeApplied;
  if (payable < PAYOUT_MINIMUM_CENTS) {
    return { error: "below_payout_minimum", payable_cents: payable, status: 409 };
  }

  const payoutId = crypto.randomUUID();
  const now = nowSeconds();
  const statements = [
    env.DB.prepare(
      `INSERT INTO affiliate_payouts
        (id, affiliate_id, amount_cents, status, reconciliation_snapshot_id,
         prepared_by, prepared_at, updated_at, negative_balance_applied_cents)
       VALUES (?, ?, ?, 'prepared', ?, ?, ?, ?, ?)`,
    ).bind(
      payoutId,
      affiliateId,
      payable,
      reconciliation.id,
      actor,
      now,
      now,
      negativeApplied,
    ),
  ];

  for (const commission of commissions.results || []) {
    const available = Number(commission.commission_cents) - Number(commission.settled_cents || 0);
    if (available <= 0) continue;
    statements.push(
      env.DB.prepare(
        `INSERT INTO affiliate_payout_allocations
          (id, payout_id, commission_id, amount_cents, created_at)
         VALUES (?, ?, ?, ?, ?)`,
      ).bind(crypto.randomUUID(), payoutId, commission.id, available, now),
    );
  }
  await env.DB.batch(statements);
  await appendAudit(env, actor, "payout_prepared", "payout", payoutId, {
    affiliate_id: affiliateId,
    gross_available_cents: grossAvailable,
    negative_balance_applied_cents: negativeApplied,
    payout_cents: payable,
    reconciliation_snapshot_id: reconciliation.id,
  });
  return { payout_id: payoutId, amount_cents: payable, status: "prepared" };
}

export async function approveAffiliatePayout(env, payoutId, actor) {
  const reconciliation = await runReconciliation(env, actor);
  if (reconciliation.status !== "ok") return { error: "payouts_frozen", status: 409 };
  const payout = await env.DB.prepare(`SELECT * FROM affiliate_payouts WHERE id = ?`).bind(payoutId).first();
  if (!payout || payout.status !== "prepared") return { error: "payout_not_prepared", status: 409 };
  if (payout.prepared_by === actor) return { error: "maker_checker_violation", status: 409 };

  const now = nowSeconds();
  const result = await env.DB.prepare(
    `UPDATE affiliate_payouts
        SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ?,
            reconciliation_snapshot_id = ?
      WHERE id = ? AND status = 'prepared'`,
  )
    .bind(actor, now, now, reconciliation.id, payoutId)
    .run();
  if ((result.meta?.changes || 0) !== 1) return { error: "payout_state_changed", status: 409 };
  await appendAudit(env, actor, "payout_approved", "payout", payoutId, {
    reconciliation_snapshot_id: reconciliation.id,
  });
  return { payout_id: payoutId, status: "approved" };
}

export async function markAffiliatePayoutPaid(env, payoutId, actor, externalReference) {
  const reconciliation = await runReconciliation(env, actor);
  if (reconciliation.status !== "ok") return { error: "payouts_frozen", status: 409 };
  const payout = await env.DB.prepare(`SELECT * FROM affiliate_payouts WHERE id = ?`).bind(payoutId).first();
  if (!payout || payout.status !== "approved") return { error: "payout_not_approved", status: 409 };
  if (!externalReference || String(externalReference).trim().length < 3) {
    return { error: "external_reference_required", status: 400 };
  }

  const allocations = await env.DB.prepare(
    `SELECT a.*, c.commission_cents, c.settled_cents, c.status AS commission_status
       FROM affiliate_payout_allocations a
       JOIN affiliate_commissions c ON c.id = a.commission_id
      WHERE a.payout_id = ?`,
  )
    .bind(payoutId)
    .all();
  const allocationTotal = (allocations.results || []).reduce((sum, row) => sum + Number(row.amount_cents), 0);
  if (allocationTotal - Number(payout.negative_balance_applied_cents || 0) !== Number(payout.amount_cents)) {
    await env.DB.prepare(
      `UPDATE affiliate_controls SET payout_frozen = 1, freeze_reason = ?, frozen_at = ?, updated_at = ? WHERE id = 'global'`,
    )
      .bind(`Payout ${payoutId} allocation mismatch`, nowSeconds(), nowSeconds())
      .run();
    return { error: "allocation_mismatch", status: 409 };
  }

  const now = nowSeconds();
  const statements = [];
  for (const allocation of allocations.results || []) {
    const nextSettled = Number(allocation.settled_cents || 0) + Number(allocation.amount_cents);
    if (nextSettled > Number(allocation.commission_cents)) {
      return { error: "allocation_exceeds_commission", status: 409 };
    }
    statements.push(
      env.DB.prepare(
        `UPDATE affiliate_commissions
            SET settled_cents = settled_cents + ?,
                status = CASE WHEN settled_cents + ? >= commission_cents THEN 'paid' ELSE status END,
                payout_id = ?, updated_at = ?
          WHERE id = ? AND status IN ('approved', 'paid')`,
      ).bind(allocation.amount_cents, allocation.amount_cents, payoutId, now, allocation.commission_id),
    );
  }
  statements.push(
    env.DB.prepare(
      `UPDATE affiliates
          SET lifetime_paid_cents = lifetime_paid_cents + ?,
              negative_balance_cents = MAX(negative_balance_cents - ?, 0),
              updated_at = ?, version = version + 1
        WHERE id = ?`,
    ).bind(payout.amount_cents, payout.negative_balance_applied_cents || 0, now, payout.affiliate_id),
    env.DB.prepare(
      `UPDATE affiliate_payouts
          SET status = 'paid', external_reference = ?, paid_at = ?, updated_at = ?,
              reconciliation_snapshot_id = ?
        WHERE id = ? AND status = 'approved'`,
    ).bind(String(externalReference).trim().slice(0, 200), now, now, reconciliation.id, payoutId),
  );
  await env.DB.batch(statements);

  await appendLedger(
    env,
    payout.affiliate_id,
    "payout_paid",
    -Number(payout.amount_cents),
    "payout",
    payoutId,
    actor,
  );
  await appendAudit(env, actor, "payout_marked_paid", "payout", payoutId, {
    amount_cents: payout.amount_cents,
    external_reference: String(externalReference).trim().slice(0, 200),
    reconciliation_snapshot_id: reconciliation.id,
  });
  return { payout_id: payoutId, status: "paid", amount_cents: payout.amount_cents };
}

export async function partnerDashboardData(env, affiliateId) {
  const affiliate = await env.DB.prepare(
    `SELECT id, slug, code, display_name, email, country, website, status,
            approved_sale_count, lifetime_approved_cents, lifetime_paid_cents,
            negative_balance_cents, created_at
       FROM affiliates WHERE id = ?`,
  )
    .bind(affiliateId)
    .first();
  if (!affiliate) return null;
  const stats = await env.DB.prepare(
    `SELECT
       (SELECT COUNT(*) FROM affiliate_clicks WHERE affiliate_id = ?) AS clicks,
       (SELECT COUNT(*) FROM affiliate_checkout_intents WHERE affiliate_id = ?) AS checkouts,
       (SELECT COUNT(*) FROM affiliate_commissions WHERE affiliate_id = ? AND status = 'pending') AS pending_sales,
       (SELECT COUNT(*) FROM affiliate_commissions WHERE affiliate_id = ? AND status IN ('approved', 'paid')) AS approved_sales,
       (SELECT COUNT(*) FROM affiliate_commissions WHERE affiliate_id = ? AND status IN ('reversed', 'rejected', 'disputed')) AS reversed_sales,
       (SELECT COALESCE(SUM(commission_cents - settled_cents), 0)
          FROM affiliate_commissions WHERE affiliate_id = ? AND status = 'approved') AS unpaid_commission_cents`,
  )
    .bind(affiliateId, affiliateId, affiliateId, affiliateId, affiliateId, affiliateId)
    .first();
  const payouts = await env.DB.prepare(
    `SELECT id, amount_cents, status, prepared_at, approved_at, paid_at, external_reference
       FROM affiliate_payouts WHERE affiliate_id = ? ORDER BY prepared_at DESC LIMIT 50`,
  )
    .bind(affiliateId)
    .all();
  const nextSaleNumber = Number(affiliate.approved_sale_count || 0) + 1;
  return {
    affiliate,
    stats: {
      clicks: Number(stats?.clicks || 0),
      checkouts: Number(stats?.checkouts || 0),
      pending_sales: Number(stats?.pending_sales || 0),
      approved_sales: Number(stats?.approved_sales || 0),
      reversed_sales: Number(stats?.reversed_sales || 0),
      unpaid_commission_cents: Number(stats?.unpaid_commission_cents || 0),
      payable_cents: Math.max(
        0,
        Number(stats?.unpaid_commission_cents || 0) - Number(affiliate.negative_balance_cents || 0),
      ),
      current_commission_cents: commissionForSaleNumber(Math.max(1, Number(affiliate.approved_sale_count || 0))),
      next_commission_cents: commissionForSaleNumber(nextSaleNumber),
      next_sale_number: nextSaleNumber,
    },
    payouts: payouts.results || [],
  };
}
