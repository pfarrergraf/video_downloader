// Returns the release metadata JSON (version, SHA-256, etc.) stored in R2.
// Uploaded by android-release.yml as DownloadThat-release.json after each build.
// Used by android-beta.html and security.html to display the current SHA-256
// without linking to GitHub (which may be a private repository).

export async function onRequestGet({ env }) {
  const obj = await env.RELEASES.get("DownloadThat-release.json");
  if (!obj) {
    return new Response(
      JSON.stringify({ error: "Release info not yet available" }),
      { status: 404, headers: { "Content-Type": "application/json" } }
    );
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  headers.set("Cache-Control", "max-age=300");
  return new Response(obj.body, { status: 200, headers });
}
