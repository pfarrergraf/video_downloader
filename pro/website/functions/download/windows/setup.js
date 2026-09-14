import { fetchWindowsAsset } from "../_windows_asset.js";

export async function onRequestGet() {
  const { upstream, filename } = await fetchWindowsAsset("GET");
  if (!upstream.ok) return new Response("Download temporarily unavailable", { status: 502 });

  const headers = new Headers({
    "Content-Type": "application/octet-stream",
    "Content-Disposition": `attachment; filename="${filename}"`,
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
  });
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) headers.set("Content-Length", contentLength);
  return new Response(upstream.body, { status: 200, headers });
}

export async function onRequestHead() {
  const { upstream } = await fetchWindowsAsset("HEAD");
  const headers = new Headers({
    "Content-Type": "application/octet-stream",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
  });
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) headers.set("Content-Length", contentLength);
  return new Response(null, { status: upstream.ok ? 200 : 502, headers });
}
