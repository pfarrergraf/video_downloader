// Provider-neutral security headers for every Pages response. No affiliate
// links/scripts are injected into otherwise static pages.
const DEFAULT_CANONICAL_ORIGIN = "https://downloadthat.app";
const REDIRECTABLE_HOSTS = new Set(["www.downloadthat.app", "downloadthat.pages.dev"]);

export async function onRequest({ request, env, next }) {
  const requestUrl = new URL(request.url);
  const canonicalOrigin = env.PUBLIC_BASE_URL || DEFAULT_CANONICAL_ORIGIN;
  const redirectsEnabled = env.CANONICAL_REDIRECT_ENABLED === "true";
  if (
    redirectsEnabled &&
    (request.method === "GET" || request.method === "HEAD") &&
    REDIRECTABLE_HOSTS.has(requestUrl.hostname)
  ) {
    const target = new URL(requestUrl.pathname + requestUrl.search, canonicalOrigin);
    return Response.redirect(target, 308);
  }

  const response = await next();
  const secured = new Response(response.body, response);
  secured.headers.set("X-Content-Type-Options", "nosniff");
  secured.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  secured.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  secured.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  return secured;
}
