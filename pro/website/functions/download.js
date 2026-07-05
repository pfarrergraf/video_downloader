// Serves the APK from Cloudflare R2 — GitHub is never contacted by the client.
// The R2 bucket "downloadthat-releases" is bound as RELEASES in wrangler.toml.
// Upload the artifact to R2 via the android-release.yml workflow step before
// this Function will return a real file; until then it returns 502.

export async function onRequestGet({ env }) {
  const obj = await env.RELEASES.get("DownloadThat-latest.apk");
  if (!obj) {
    return new Response("Download temporarily unavailable", { status: 502 });
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/vnd.android.package-archive");
  headers.set("Content-Disposition", 'attachment; filename="DownloadThat.apk"');
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  if (obj.size) {
    headers.set("Content-Length", String(obj.size));
  }

  return new Response(obj.body, { status: 200, headers });
}

export async function onRequestHead({ env }) {
  const obj = await env.RELEASES.head("DownloadThat-latest.apk");
  const headers = new Headers();
  headers.set("Content-Type", "application/vnd.android.package-archive");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  if (obj && obj.size) {
    headers.set("Content-Length", String(obj.size));
  }
  return new Response(null, { status: obj ? 200 : 502, headers });
}
