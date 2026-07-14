(function () {
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
  function updatePlayStatus(language) {
    const isGerman = String(language || document.documentElement.lang || navigator.language).toLowerCase().startsWith("de");
    document.querySelectorAll("[data-play-status]").forEach((node) => {
      node.textContent = playReady
        ? (isGerman ? "Google Play ist verfügbar." : "Google Play is available.")
        : (isGerman ? "Der Google-Play-Link wird zum Start freigeschaltet." : "The Google Play link will be enabled for launch.");
    });
  }
  updatePlayStatus();
  window.addEventListener("downloadthat:languagechange", (event) => updatePlayStatus(event.detail.language));
  document.querySelectorAll("[data-direct-apk-link]").forEach((link) => {
    link.href = config.DIRECT_APK_URL || "/download/direct/apk";
  });
  document.querySelectorAll("[data-direct-sha-link]").forEach((link) => {
    link.href = config.DIRECT_APK_SHA256_URL || "/download/direct/sha256";
  });
})();
