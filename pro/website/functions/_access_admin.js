const textEncoder = new TextEncoder();
const jwksCache = new Map();
const JWKS_CACHE_MS = 5 * 60 * 1000;

function normalizeTeamDomain(value) {
  const raw = String(value || "").trim().replace(/\/+$/, "");
  if (!raw) return "";
  if (!raw.startsWith("https://")) return `https://${raw}`;
  return raw;
}

function base64UrlToBytes(value) {
  const normalized = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4 || 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function decodeJsonPart(value) {
  const bytes = base64UrlToBytes(value);
  return JSON.parse(new TextDecoder().decode(bytes));
}

function audienceMatches(claim, expected) {
  if (Array.isArray(claim)) return claim.includes(expected);
  return claim === expected;
}

async function fetchJwks(teamDomain, fetchImpl) {
  const cached = jwksCache.get(teamDomain);
  if (cached && Date.now() - cached.fetchedAt < JWKS_CACHE_MS) return cached.jwks;

  const response = await fetchImpl(`${teamDomain}/cdn-cgi/access/certs`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`Access JWKS fetch failed: ${response.status}`);
  const jwks = await response.json();
  if (!Array.isArray(jwks?.keys) || jwks.keys.length === 0) throw new Error("Access JWKS contains no keys");
  jwksCache.set(teamDomain, { fetchedAt: Date.now(), jwks });
  return jwks;
}

async function verifyRs256(signingInput, signature, jwk) {
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  return crypto.subtle.verify(
    { name: "RSASSA-PKCS1-v1_5" },
    key,
    signature,
    textEncoder.encode(signingInput),
  );
}

export async function verifyCloudflareAccessAdmin(request, env, options = {}) {
  const teamDomain = normalizeTeamDomain(env.CLOUDFLARE_ACCESS_TEAM_DOMAIN);
  const audience = String(env.CLOUDFLARE_ACCESS_AUD || "").trim();
  const allowedEmail = String(env.TESTER_GRANTS_ADMIN_EMAIL || "").trim().toLowerCase();
  if (!teamDomain || !audience || !allowedEmail) {
    return { ok: false, status: 503, error: "admin_access_not_configured" };
  }

  const token = String(request.headers.get("Cf-Access-Jwt-Assertion") || "").trim();
  if (!token) return { ok: false, status: 403, error: "missing_access_token" };

  const parts = token.split(".");
  if (parts.length !== 3) return { ok: false, status: 403, error: "invalid_access_token" };

  let header;
  let payload;
  try {
    header = decodeJsonPart(parts[0]);
    payload = decodeJsonPart(parts[1]);
  } catch {
    return { ok: false, status: 403, error: "invalid_access_token" };
  }

  if (header.alg !== "RS256" || typeof header.kid !== "string" || !header.kid) {
    return { ok: false, status: 403, error: "invalid_access_token" };
  }

  const now = Math.floor((options.nowMs ?? Date.now()) / 1000);
  const issuer = String(payload.iss || "").replace(/\/+$/, "");
  const email = String(payload.email || "").trim().toLowerCase();
  if (
    issuer !== teamDomain ||
    !audienceMatches(payload.aud, audience) ||
    !Number.isFinite(payload.exp) || payload.exp <= now ||
    (Number.isFinite(payload.nbf) && payload.nbf > now) ||
    email !== allowedEmail
  ) {
    return { ok: false, status: 403, error: "access_denied" };
  }

  try {
    const fetchImpl = options.fetchImpl || fetch;
    const jwks = await fetchJwks(teamDomain, fetchImpl);
    const jwk = jwks.keys.find((candidate) => candidate.kid === header.kid);
    if (!jwk) return { ok: false, status: 403, error: "invalid_access_token" };
    const verified = await verifyRs256(
      `${parts[0]}.${parts[1]}`,
      base64UrlToBytes(parts[2]),
      jwk,
    );
    if (!verified) return { ok: false, status: 403, error: "invalid_access_token" };
  } catch {
    return { ok: false, status: 503, error: "access_verification_unavailable" };
  }

  return { ok: true, email };
}
