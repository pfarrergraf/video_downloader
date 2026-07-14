import { sha256Hex } from "./_lib.js";

const DEFAULT_PACKAGE_NAME = "de.classydl.app";
const DEFAULT_PRODUCT_ID = "pro";
const PLAY_SCOPE = "https://www.googleapis.com/auth/androidpublisher";
const TOKEN_URL = "https://oauth2.googleapis.com/token";
const PLAY_API = "https://androidpublisher.googleapis.com/androidpublisher/v3";
const OIDC_ISSUERS = new Set(["accounts.google.com", "https://accounts.google.com"]);
let cachedAccessToken = null;
let accessTokenRequest = null;

function bytesToBase64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function stringToBase64Url(value) {
  return bytesToBase64Url(new TextEncoder().encode(value));
}

function base64UrlToBytes(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function pemToBytes(pem) {
  const body = pem.replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g, "");
  return Uint8Array.from(atob(body), (char) => char.charCodeAt(0));
}

function timingSafeTextEqual(left, right) {
  if (typeof left !== "string" || typeof right !== "string" || left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function expectedConfig(env) {
  return {
    packageName: env.PLAY_PACKAGE_NAME || DEFAULT_PACKAGE_NAME,
    productId: env.PLAY_PRODUCT_ID || DEFAULT_PRODUCT_ID,
  };
}

function licenseKeyForTokenHash(tokenHash) {
  const hex = tokenHash.slice(0, 24).toUpperCase();
  return `DLT-${hex.slice(0, 8)}-${hex.slice(8, 16)}-${hex.slice(16, 24)}`;
}

async function importServiceAccountKey(privateKey) {
  return crypto.subtle.importKey(
    "pkcs8",
    pemToBytes(privateKey),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

async function serviceAccountAccessToken(env, fetchImpl = fetch) {
  if (!env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL || !env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY) {
    throw new Error("Google Play service account is not configured");
  }
  const now = Math.floor(Date.now() / 1000);
  const principal = env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL;
  if (cachedAccessToken?.principal === principal && cachedAccessToken.expiresAt > now + 60) {
    return cachedAccessToken.token;
  }
  // Coalesce a burst of purchase/acknowledgement calls in the same Worker
  // isolate into one OAuth exchange. This matters during launches and RTDN
  // catch-up, where thousands of requests can arrive together.
  if (accessTokenRequest?.principal === principal) return accessTokenRequest.promise;
  const promise = (async () => {
  const header = stringToBase64Url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims = stringToBase64Url(
    JSON.stringify({
      iss: env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL,
      scope: PLAY_SCOPE,
      aud: TOKEN_URL,
      iat: now,
      exp: now + 3600,
    }),
  );
  const signingInput = `${header}.${claims}`;
  const key = await importServiceAccountKey(env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY.replace(/\\n/g, "\n"));
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(signingInput),
  );
  const assertion = `${signingInput}.${bytesToBase64Url(new Uint8Array(signature))}`;
  const response = await fetchImpl(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion }),
  });
  if (!response.ok) throw new Error(`Google OAuth token request failed: ${response.status}`);
  const body = await response.json();
  if (!body.access_token) throw new Error("Google OAuth response omitted access_token");
  cachedAccessToken = {
    token: body.access_token,
    principal,
    expiresAt: now + Math.max(Number(body.expires_in) || 3600, 60),
  };
  return body.access_token;
  })();
  accessTokenRequest = { principal, promise };
  try {
    return await promise;
  } finally {
    if (accessTokenRequest?.promise === promise) accessTokenRequest = null;
  }
}

async function authorizedPlayFetch(env, url, options = {}) {
  const fetchImpl = env.PLAY_FETCH || fetch;
  const accessToken = env.PLAY_ACCESS_TOKEN_FOR_TESTS || (await serviceAccountAccessToken(env, fetchImpl));
  return fetchImpl(url, {
    ...options,
    headers: { ...(options.headers || {}), Authorization: `Bearer ${accessToken}` },
  });
}

export async function fetchPlayPurchase(env, purchaseToken) {
  const { packageName } = expectedConfig(env);
  const url = `${PLAY_API}/applications/${encodeURIComponent(packageName)}/purchases/productsv2/tokens/${encodeURIComponent(purchaseToken)}`;
  const response = await authorizedPlayFetch(env, url);
  if (!response.ok) {
    const error = new Error(`Google Play purchase verification failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function normalizePurchase(purchase) {
  const lineItem = purchase.productLineItem?.[0] || purchase.productLineItems?.[0] || purchase.lineItems?.[0] || {};
  return {
    state: purchase.purchaseStateContext?.purchaseState || purchase.purchaseState || "UNKNOWN",
    productId: lineItem.productId || purchase.productId || null,
    orderId: lineItem.latestSuccessfulOrderId || purchase.orderId || null,
    acknowledged:
      purchase.acknowledgementState === "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED" ||
      purchase.acknowledgementState === 1,
  };
}

function stateKind(state) {
  if (state === "PURCHASED" || state === "PURCHASE_STATE_PURCHASED") return "purchased";
  if (state === "PENDING" || state === "PURCHASE_STATE_PENDING") return "pending";
  return "revoked";
}

function encryptionKeyBytes(env) {
  if (!env.PLAY_TOKEN_ENCRYPTION_KEY) throw new Error("PLAY_TOKEN_ENCRYPTION_KEY is not configured");
  const bytes = Uint8Array.from(atob(env.PLAY_TOKEN_ENCRYPTION_KEY), (char) => char.charCodeAt(0));
  if (bytes.length !== 32) throw new Error("PLAY_TOKEN_ENCRYPTION_KEY must be a base64-encoded 32-byte key");
  return bytes;
}

async function tokenEncryptionKey(env, usage) {
  return crypto.subtle.importKey("raw", encryptionKeyBytes(env), "AES-GCM", false, usage);
}

export async function encryptPurchaseToken(env, purchaseToken) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await tokenEncryptionKey(env, ["encrypt"]);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(purchaseToken),
  );
  return {
    ciphertext: bytesToBase64Url(new Uint8Array(ciphertext)),
    iv: bytesToBase64Url(iv),
  };
}

export async function decryptPurchaseToken(env, ciphertext, iv) {
  const key = await tokenEncryptionKey(env, ["decrypt"]);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64UrlToBytes(iv) },
    key,
    base64UrlToBytes(ciphertext),
  );
  return new TextDecoder().decode(plaintext);
}

export async function acknowledgePlayPurchase(env, purchaseToken, productId) {
  const { packageName } = expectedConfig(env);
  const url = `${PLAY_API}/applications/${encodeURIComponent(packageName)}/purchases/products/${encodeURIComponent(productId)}/tokens/${encodeURIComponent(purchaseToken)}:acknowledge`;
  const response = await authorizedPlayFetch(env, url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) throw new Error(`Google Play acknowledgement failed: ${response.status}`);
}

async function storeUnentitledPurchase(env, tokenHash, encrypted, normalized, now) {
  const { packageName, productId } = expectedConfig(env);
  const status = stateKind(normalized.state);
  await env.DB.prepare(
    `INSERT INTO play_purchases
       (token_hash, purchase_token_ciphertext, purchase_token_iv, order_id, package_name,
        product_id, purchase_state, license_key, verified_at, acknowledged_at, revoked_at, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?, ?)
     ON CONFLICT(token_hash) DO UPDATE SET
       order_id = excluded.order_id, purchase_state = excluded.purchase_state,
       verified_at = excluded.verified_at, revoked_at = excluded.revoked_at, updated_at = excluded.updated_at`,
  )
    .bind(
      tokenHash,
      encrypted.ciphertext,
      encrypted.iv,
      normalized.orderId,
      packageName,
      productId,
      status,
      now,
      status === "revoked" ? now : null,
      now,
      now,
    )
    .run();
  if (status === "revoked") {
    await env.DB.prepare(
      `UPDATE licenses SET status = 'canceled', updated_at = ?
       WHERE license_key = (SELECT license_key FROM play_purchases WHERE token_hash = ?)`,
    ).bind(now, tokenHash).run();
  }
  return { entitled: false, state: status };
}

async function grantPurchasedEntitlement(env, purchaseToken, tokenHash, encrypted, normalized, now) {
  const config = expectedConfig(env);
  let mapping = await env.DB.prepare(
    `SELECT license_key, acknowledged_at FROM play_purchases WHERE token_hash = ?`,
  ).bind(tokenHash).first();

  if (!mapping?.license_key) {
    // Purchase tokens are high-entropy Google credentials and their SHA-256
    // hash is never exposed. A deterministic key closes the last race where
    // two concurrent first-time verifications could otherwise mint an orphan
    // second license before the unique token mapping wins.
    const licenseKey = licenseKeyForTokenHash(tokenHash);
    try {
      await env.DB.batch([
        env.DB.prepare(
          `INSERT OR IGNORE INTO licenses
             (license_key, tier, email, status, provider, provider_subject, created_at, updated_at)
           VALUES (?, 'lifetime', ?, 'active', 'google_play', ?, ?, ?)`,
        ).bind(licenseKey, `play-${tokenHash}@local.invalid`, tokenHash, now, now),
        env.DB.prepare(
          `INSERT INTO play_purchases
             (token_hash, purchase_token_ciphertext, purchase_token_iv, order_id, package_name,
              product_id, purchase_state, license_key, verified_at, acknowledged_at, revoked_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'purchased', ?, ?, NULL, NULL, ?, ?)
           ON CONFLICT(token_hash) DO UPDATE SET
             order_id = excluded.order_id, purchase_state = 'purchased',
             license_key = COALESCE(play_purchases.license_key, excluded.license_key),
             verified_at = excluded.verified_at, revoked_at = NULL, updated_at = excluded.updated_at`,
        ).bind(
          tokenHash,
          encrypted.ciphertext,
          encrypted.iv,
          normalized.orderId,
          config.packageName,
          config.productId,
          licenseKey,
          now,
          now,
          now,
        ),
      ]);
    } catch (error) {
      mapping = await env.DB.prepare(
        `SELECT license_key, acknowledged_at FROM play_purchases WHERE token_hash = ?`,
      ).bind(tokenHash).first();
      if (!mapping?.license_key) throw error;
    }
    mapping = await env.DB.prepare(
      `SELECT license_key, acknowledged_at FROM play_purchases WHERE token_hash = ?`,
    ).bind(tokenHash).first();
  } else {
    await env.DB.batch([
      env.DB.prepare(
        `UPDATE play_purchases SET order_id = ?, purchase_state = 'purchased', verified_at = ?,
         revoked_at = NULL, updated_at = ? WHERE token_hash = ?`,
      ).bind(normalized.orderId, now, now, tokenHash),
      env.DB.prepare(`UPDATE licenses SET status = 'active', updated_at = ? WHERE license_key = ?`)
        .bind(now, mapping.license_key),
    ]);
  }

  let acknowledged = normalized.acknowledged || mapping?.acknowledged_at != null;
  if (!acknowledged) {
    try {
      await acknowledgePlayPurchase(env, purchaseToken, config.productId);
      await env.DB.prepare(
        `UPDATE play_purchases SET acknowledged_at = ?, updated_at = ? WHERE token_hash = ?`,
      ).bind(now, now, tokenHash).run();
      acknowledged = true;
    } catch (error) {
      console.error("Google Play acknowledgement deferred", { tokenHash, message: String(error?.message || error) });
    }
  }
  return {
    entitled: true,
    state: "purchased",
    licenseKey: mapping.license_key,
    acknowledged,
    verifiedAt: now,
    offlineGraceSeconds: 72 * 3600,
  };
}

export async function verifyAndApplyPlayPurchase(env, purchaseToken, supplied = {}) {
  if (!env.DB) throw new Error("DB (D1) binding is not configured");
  if (typeof purchaseToken !== "string" || purchaseToken.length < 16 || purchaseToken.length > 4096) {
    const error = new Error("invalid purchase token");
    error.status = 400;
    throw error;
  }
  const config = expectedConfig(env);
  if (
    (supplied.packageName && !timingSafeTextEqual(supplied.packageName, config.packageName)) ||
    (supplied.productId && !timingSafeTextEqual(supplied.productId, config.productId))
  ) {
    const error = new Error("unexpected package or product");
    error.status = 400;
    throw error;
  }
  const purchase = await fetchPlayPurchase(env, purchaseToken);
  const normalized = normalizePurchase(purchase);
  if (!normalized.productId || !timingSafeTextEqual(normalized.productId, config.productId)) {
    const error = new Error("verified purchase belongs to an unexpected product");
    error.status = 403;
    throw error;
  }
  const tokenHash = await sha256Hex(purchaseToken);
  const encrypted = await encryptPurchaseToken(env, purchaseToken);
  const now = Math.floor(Date.now() / 1000);
  if (stateKind(normalized.state) !== "purchased") {
    return storeUnentitledPurchase(env, tokenHash, encrypted, normalized, now);
  }
  return grantPurchasedEntitlement(env, purchaseToken, tokenHash, encrypted, normalized, now);
}

export async function revokePlayPurchaseByToken(env, purchaseToken) {
  const tokenHash = await sha256Hex(purchaseToken);
  const now = Math.floor(Date.now() / 1000);
  const row = await env.DB.prepare(`SELECT license_key FROM play_purchases WHERE token_hash = ?`)
    .bind(tokenHash).first();
  if (!row) return false;
  await env.DB.batch([
    env.DB.prepare(
      `UPDATE play_purchases SET purchase_state = 'revoked', revoked_at = ?, verified_at = ?, updated_at = ?
       WHERE token_hash = ?`,
    ).bind(now, now, now, tokenHash),
    env.DB.prepare(`UPDATE licenses SET status = 'canceled', updated_at = ? WHERE license_key = ?`)
      .bind(now, row.license_key),
  ]);
  return true;
}

export async function verifyGoogleOidcJwt(jwt, env, fetchImpl = fetch) {
  if (!env.PLAY_RTDN_AUDIENCE || !env.PLAY_RTDN_SERVICE_ACCOUNT_EMAIL) {
    throw new Error("RTDN OIDC audience/service account is not configured");
  }
  const parts = String(jwt || "").split(".");
  if (parts.length !== 3) return null;
  const header = JSON.parse(new TextDecoder().decode(base64UrlToBytes(parts[0])));
  const claims = JSON.parse(new TextDecoder().decode(base64UrlToBytes(parts[1])));
  if (header.alg !== "RS256" || !header.kid) return null;
  const now = Math.floor(Date.now() / 1000);
  if (
    !OIDC_ISSUERS.has(claims.iss) ||
    claims.aud !== env.PLAY_RTDN_AUDIENCE ||
    claims.email !== env.PLAY_RTDN_SERVICE_ACCOUNT_EMAIL ||
    claims.email_verified !== true ||
    !Number.isFinite(claims.exp) || claims.exp < now ||
    !Number.isFinite(claims.iat) || claims.iat > now + 60
  ) return null;
  const response = await fetchImpl("https://www.googleapis.com/oauth2/v3/certs");
  if (!response.ok) throw new Error(`Google OIDC JWKS fetch failed: ${response.status}`);
  const jwks = await response.json();
  const jwk = jwks.keys?.find((candidate) => candidate.kid === header.kid && candidate.alg === "RS256");
  if (!jwk) return null;
  const key = await crypto.subtle.importKey(
    "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
  );
  const valid = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    base64UrlToBytes(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  return valid ? claims : null;
}

export async function reconcilePlayPurchases(env, limit = 100) {
  const rows = await env.DB.prepare(
    `SELECT token_hash, purchase_token_ciphertext, purchase_token_iv
     FROM play_purchases ORDER BY verified_at ASC LIMIT ?`,
  ).bind(Math.min(Math.max(Number(limit) || 100, 1), 1000)).all();
  const summary = { checked: 0, entitled: 0, revoked: 0, failed: 0 };
  for (const row of rows.results || []) {
    let token;
    try {
      token = await decryptPurchaseToken(env, row.purchase_token_ciphertext, row.purchase_token_iv);
      const result = await verifyAndApplyPlayPurchase(env, token);
      summary.checked += 1;
      if (result.entitled) summary.entitled += 1;
      else if (result.state === "revoked") summary.revoked += 1;
    } catch (error) {
      // A token which was verified previously but is now gone is no longer a
      // defensible entitlement. This is the reconciliation fallback for a
      // missed cancellation/refund RTDN. Other API failures remain retriable
      // and do not revoke on a transient Google outage.
      if ((error?.status === 404 || error?.status === 410) && token) {
        await revokePlayPurchaseByToken(env, token);
        summary.checked += 1;
        summary.revoked += 1;
        continue;
      }
      summary.failed += 1;
      console.error("Google Play reconciliation item failed", { tokenHash: row.token_hash, message: String(error?.message || error) });
    }
  }
  return summary;
}
