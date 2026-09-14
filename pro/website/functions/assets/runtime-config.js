const RELEASE_API_URL =
  "https://api.github.com/repos/pfarrergraf/video_downloader/releases/latest";
const FALLBACK_RELEASE_VERSION = "1.0.3";
const FALLBACK_RELEASE_TAG = "v1.0.3";
// PLAY_STORE_VERSION and DIRECT_RELEASE_HIGHLIGHTS are set by the protected
// Pages deployment workflow when a new sideload/Play comparison is approved.
const DEFAULT_RELEASE_HIGHLIGHTS = {
  en: [
    "Signed sideload builds are available as a separate distribution channel.",
    "The yt-dlp download engine can update independently of the app package.",
    "Version-specific changes are linked in the release notes.",
  ],
  de: [
    "Signierte Sideload-Builds stehen als separater Vertriebskanal zur Verfügung.",
    "Die yt-dlp-Download-Engine kann unabhängig vom App-Paket aktualisiert werden.",
    "Versionsspezifische Änderungen stehen in den Release Notes.",
  ],
};

function releaseVersion(tag) {
  const match = String(tag || "").match(/(\d+(?:\.\d+){2,3})/);
  return match ? match[1] : FALLBACK_RELEASE_VERSION;
}

function configuredHighlights(env) {
  const raw = env?.DIRECT_RELEASE_HIGHLIGHTS;
  if (typeof raw !== "string" || !raw.trim()) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

async function latestRelease() {
  try {
    const response = await fetch(RELEASE_API_URL, {
      headers: { Accept: "application/vnd.github+json", "User-Agent": "DownloadThat-website" },
    });
    if (!response.ok) throw new Error(`GitHub release lookup failed: ${response.status}`);
    const release = await response.json();
    const tag = typeof release.tag_name === "string" ? release.tag_name : FALLBACK_RELEASE_TAG;
    const assets = Array.isArray(release.assets) ? release.assets : [];
    return {
      version: releaseVersion(tag),
      tag,
      url: typeof release.html_url === "string" ? release.html_url : "",
      installerAvailable: assets.some((asset) => asset?.name === "DownloadThat-latest-Setup.exe"),
    };
  } catch {
    return {
      version: FALLBACK_RELEASE_VERSION,
      tag: FALLBACK_RELEASE_TAG,
      url: "https://github.com/pfarrergraf/video_downloader/releases/latest",
      installerAvailable: false,
    };
  }
}

export async function onRequestGet({ env }) {
  const playStoreUrl = typeof env?.PLAY_STORE_URL === "string" ? env.PLAY_STORE_URL : "";
  const release = await latestRelease();
  const highlights = configuredHighlights(env);
  const body = `window.DOWNLOADTHAT_CONFIG = Object.freeze(${JSON.stringify({
    PLAY_STORE_URL: playStoreUrl,
    PLAY_STORE_VERSION: typeof env?.PLAY_STORE_VERSION === "string" && env.PLAY_STORE_VERSION
      ? env.PLAY_STORE_VERSION
      : FALLBACK_RELEASE_VERSION,
    DIRECT_APK_URL: "/download/direct/apk",
    DIRECT_APK_SHA256_URL: "/download/direct/sha256",
    WINDOWS_URL: "/download/windows/setup",
    WINDOWS_SHA256_URL: "/download/windows/sha256",
    RELEASE_VERSION: release.version,
    RELEASE_TAG: release.tag,
    RELEASE_URL: release.url,
    WINDOWS_INSTALLER_AVAILABLE: release.installerAvailable,
    RELEASE_HIGHLIGHTS: Object.keys(highlights).length ? highlights : DEFAULT_RELEASE_HIGHLIGHTS,
  })});\n`;
  return new Response(body, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=300",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
