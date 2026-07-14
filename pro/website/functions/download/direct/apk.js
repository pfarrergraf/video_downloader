const APK_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.apk";

async function proxy(method) {
  const upstream = await fetch(APK_URL, { method, redirect: "follow" });
  if (!upstream.ok) return new Response("Download temporarily unavailable", { status: 502 });
  const headers = new Headers({
    "Content-Type": "application/vnd.android.package-archive",
    "Content-Disposition": 'attachment; filename="DownloadThat.apk"',
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
  });
  const length = upstream.headers.get("Content-Length");
  if (length) headers.set("Content-Length", length);
  return new Response(method === "HEAD" ? null : upstream.body, { status: 200, headers });
}

export async function onRequestGet() {
  return proxy("GET");
}

export async function onRequestHead() {
  return proxy("HEAD");
}
