import { fetchWindowsChecksum } from "../_windows_asset.js";

export async function onRequestGet() {
  const { upstream, filename } = await fetchWindowsChecksum("GET");
  if (!upstream.ok) return new Response("Checksum temporarily unavailable", { status: 502 });

  const checksum = (await upstream.text()).replace(/\r?\n$/, "");
  const headers = new Headers({
    "Content-Type": "text/plain; charset=utf-8",
    "Content-Disposition": `attachment; filename="${filename}.sha256"`,
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
  });
  return new Response(`${checksum}\n`, { status: 200, headers });
}
