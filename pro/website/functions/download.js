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

  const headers = new Headers(upstream.headers);
  headers.set("Content-Disposition", 'attachment; filename="DownloadThat.apk"');
  headers.delete("set-cookie");

  return new Response(upstream.body, { status: 200, headers });
}
