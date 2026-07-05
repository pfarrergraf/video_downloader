// Serves the Windows EXE from Cloudflare R2 — GitHub is never contacted.
// The R2 bucket "downloadthat-releases" is bound as RELEASES in wrangler.toml.
// Upload the artifact to R2 via the windows-release.yml workflow step before
// this Function will return a real file; until then it returns 502.

export async function onRequestGet({ env }) {
  const obj = await env.RELEASES.get("DownloadThat-latest.exe");
  if (!obj) {
    return new Response("Download temporarily unavailable", { status: 502 });
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/octet-stream");
  headers.set("Content-Disposition", 'attachment; filename="DownloadThat.exe"');
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  if (obj.size) {
    headers.set("Content-Length", String(obj.size));
  }

  return new Response(obj.body, { status: 200, headers });
}

export async function onRequestHead({ env }) {
  const obj = await env.RELEASES.head("DownloadThat-latest.exe");
  const headers = new Headers();
  headers.set("Content-Type", "application/octet-stream");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  if (obj && obj.size) {
    headers.set("Content-Length", String(obj.size));
  }
  return new Response(null, { status: obj ? 200 : 502, headers });
}
