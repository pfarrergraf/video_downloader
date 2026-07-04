// Windows counterpart to download.js - same reasoning: proxy the release asset
// through our own origin instead of linking straight to GitHub, and stream
// rather than redirect so the GitHub origin never reaches the client.
const EXE_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.exe";

export async function onRequestGet() {
  const upstream = await fetch(EXE_URL, { redirect: "follow" });
  if (!upstream.ok) {
    return new Response("Download temporarily unavailable", { status: 502 });
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/octet-stream");
  headers.set("Content-Disposition", 'attachment; filename="DownloadThat.exe"');
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) {
    headers.set("Content-Length", contentLength);
  }

  return new Response(upstream.body, { status: 200, headers });
}

export async function onRequestHead() {
  const upstream = await fetch(EXE_URL, { method: "HEAD", redirect: "follow" });
  const headers = new Headers();
  headers.set("Content-Type", "application/octet-stream");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) {
    headers.set("Content-Length", contentLength);
  }
  return new Response(null, { status: upstream.ok ? 200 : 502, headers });
}
