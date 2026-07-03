// Serves the APK from our own origin instead of linking straight to GitHub —
// the download button/link should never show "github.com" in its href or in
// the browser's download UI. This streams the release asset through rather
// than issuing a redirect, so the GitHub origin never reaches the client.
const APK_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.apk";

export async function onRequestGet() {
  const upstream = await fetch(APK_URL, { redirect: "follow" });
  if (!upstream.ok) {
    return new Response("Download temporarily unavailable", { status: 502 });
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/vnd.android.package-archive");
  headers.set("Content-Disposition", 'attachment; filename="DownloadThat.apk"');
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) {
    headers.set("Content-Length", contentLength);
  }

  return new Response(upstream.body, { status: 200, headers });
}

export async function onRequestHead() {
  const upstream = await fetch(APK_URL, { method: "HEAD", redirect: "follow" });
  const headers = new Headers();
  headers.set("Content-Type", "application/vnd.android.package-archive");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) {
    headers.set("Content-Length", contentLength);
  }
  return new Response(null, { status: upstream.ok ? 200 : 502, headers });
}
