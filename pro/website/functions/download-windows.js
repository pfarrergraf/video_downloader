// Legacy endpoint kept for existing links. New pages use
// /download/windows/setup, which prefers the installer and falls back to the
// portable EXE until the next Windows release contains the installer asset.
import { fetchWindowsAsset } from "./download/_windows_asset.js";

export async function onRequestGet() {
  const { upstream, filename } = await fetchWindowsAsset("GET");
  if (!upstream.ok) {
    return new Response("Download temporarily unavailable", { status: 502 });
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/octet-stream");
  headers.set("Content-Disposition", `attachment; filename="${filename}"`);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "no-store");
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) {
    headers.set("Content-Length", contentLength);
  }

  return new Response(upstream.body, { status: 200, headers });
}

export async function onRequestHead() {
  const { upstream } = await fetchWindowsAsset("HEAD");
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
