(function () {
  const language = (navigator.language || "en").toLowerCase().startsWith("de") ? "de" : "en";
  document.documentElement.lang = language;

  const config = window.DOWNLOADTHAT_CONFIG || {};
  const playUrl = config.PLAY_STORE_URL;
  const playReady = typeof playUrl === "string" && /^https:\/\//.test(playUrl) && !playUrl.includes("__PLAY_STORE_URL__");

  document.querySelectorAll("[data-play-store-link]").forEach((link) => {
    if (playReady) {
      link.href = playUrl;
      link.removeAttribute("aria-disabled");
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    }
  });
  document.querySelectorAll("[data-play-status]").forEach((node) => {
    node.textContent = playReady
      ? (language === "de" ? "Google Play ist verfügbar." : "Google Play is available.")
      : (language === "de" ? "Google-Play-Link wird zum Start freigeschaltet." : "The Google Play link will be enabled for launch.");
  });
  document.querySelectorAll("[data-direct-apk-link]").forEach((link) => {
    link.href = config.DIRECT_APK_URL || "/download/direct/apk";
  });
  document.querySelectorAll("[data-direct-sha-link]").forEach((link) => {
    link.href = config.DIRECT_APK_SHA256_URL || "/download/direct/sha256";
  });
})();
