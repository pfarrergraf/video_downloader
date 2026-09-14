(function () {
  const config = window.DOWNLOADTHAT_CONFIG || {};
  const playUrl = config.PLAY_STORE_URL;
  const playReady = typeof playUrl === "string" && /^https:\/\//.test(playUrl) && !playUrl.includes("__PLAY_STORE_URL__");
  const fallbackVersion = "1.0.3";

  function versionParts(value) {
    return String(value || "0").split(".").map((part) => Number.parseInt(part, 10) || 0);
  }

  function compareVersions(left, right) {
    const a = versionParts(left);
    const b = versionParts(right);
    for (let index = 0; index < Math.max(a.length, b.length); index += 1) {
      if ((a[index] || 0) !== (b[index] || 0)) return (a[index] || 0) - (b[index] || 0);
    }
    return 0;
  }

  function isGerman() {
    return String(document.documentElement.lang || navigator.language).toLowerCase().startsWith("de");
  }

  function highlightsFor(language) {
    const configured = config.RELEASE_HIGHLIGHTS;
    if (!configured || typeof configured !== "object") return [];
    const values = configured[language] || configured.en;
    return Array.isArray(values) ? values.filter((value) => typeof value === "string" && value.trim()) : [];
  }

  function releaseTooltip(channel, language) {
    const latest = config.RELEASE_VERSION || fallbackVersion;
    const play = config.PLAY_STORE_VERSION || fallbackVersion;
    const highlights = highlightsFor(language);
    const windowsDetails = channel === "windows"
      ? (config.WINDOWS_INSTALLER_AVAILABLE
        ? (language === "de" ? " Der aktuelle Windows-Release enthält den Installer." : " The current Windows release contains the installer.")
        : (language === "de" ? " Bis zum nächsten Installer-Release wird die portable EXE geliefert." : " The portable EXE is served until the next installer release.") )
      : "";
    const details = `${windowsDetails} ${highlights.join(" ")}`.trim();
    if (channel === "play") {
      return language === "de"
        ? `Genehmigte Google-Play-Version ${play}.`
        : `Approved Google Play version ${play}.`;
    }
    if (compareVersions(latest, play) > 0) {
      return language === "de"
        ? `Neueste signierte Direktversion ${latest}; neuer als die genehmigte Play-Variante ${play}. Ältere Builds sind überholt.${details}`
        : `Newest signed sideload version ${latest}; newer than the approved Play version ${play}. Older builds are superseded.${details}`;
    }
    return language === "de"
      ? `Signierte Direktversion ${latest}; gleicher Stand wie die genehmigte Play-Variante ${play}. Ältere Builds sind überholt.${details}`
      : `Signed sideload version ${latest}; same version as the approved Play release ${play}. Older builds are superseded.${details}`;
  }

  function renderReleaseMetadata() {
    const language = isGerman() ? "de" : "en";
    document.querySelectorAll("[data-version-banner]").forEach((node) => {
      const channel = node.dataset.channel || "direct";
      const version = channel === "play"
        ? (config.PLAY_STORE_VERSION || node.dataset.fallbackVersion || fallbackVersion)
        : (config.RELEASE_VERSION || node.dataset.fallbackVersion || fallbackVersion);
      node.textContent = `Version ${version}`;
      const tooltip = releaseTooltip(channel, language);
      node.dataset.tooltip = tooltip;
      node.title = tooltip;
      node.setAttribute("aria-label", tooltip);
    });
  }

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
  document.querySelectorAll("[data-windows-link]").forEach((link) => {
    link.href = config.WINDOWS_URL || "/download/windows/setup";
  });
  document.querySelectorAll("[data-windows-check-link]").forEach((link) => {
    link.href = config.WINDOWS_SHA256_URL || "/download/windows/sha256";
  });
  renderReleaseMetadata();
  window.addEventListener("downloadthat:languagechange", renderReleaseMetadata);
})();
