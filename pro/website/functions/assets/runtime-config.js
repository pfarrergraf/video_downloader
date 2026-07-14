export async function onRequestGet({ env }) {
  const playStoreUrl = typeof env.PLAY_STORE_URL === "string" ? env.PLAY_STORE_URL : "";
  const body = `window.DOWNLOADTHAT_CONFIG = Object.freeze(${JSON.stringify({
    PLAY_STORE_URL: playStoreUrl,
    DIRECT_APK_URL: "/download/direct/apk",
    DIRECT_APK_SHA256_URL: "/download/direct/sha256",
  })});\n`;
  return new Response(body, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=300",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
