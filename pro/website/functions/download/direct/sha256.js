const CHECKSUM_URL =
  "https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.apk.sha256";

export async function onRequestGet() {
  const upstream = await fetch(CHECKSUM_URL, { redirect: "follow" });
  if (!upstream.ok) return new Response("Checksum temporarily unavailable", { status: 502 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Content-Disposition": 'attachment; filename="DownloadThat.apk.sha256"',
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    },
  });
}
