(function () {
  const available = new Set([
    "af", "ar-SA", "az", "be", "bg", "bn", "bs", "ca", "cs", "da", "de", "el", "en",
    "es-419", "es", "et", "eu", "fa", "fi", "fil", "fr-CA", "fr", "ga", "gl", "gu",
    "he", "hi", "hr", "hu", "hy", "id", "is", "it", "ja", "ka", "kk", "km", "kn",
    "ko", "ky", "lo", "lt", "lv", "mk", "ml", "mn", "mr", "ms-MY", "my", "nb-NO",
    "ne", "nl", "pa", "pl", "pt-BR", "pt-PT", "ro", "ru", "si", "sk", "sl", "sq",
    "sr", "sv", "sw", "ta", "te", "th", "tr", "uk", "ur", "uz", "vi", "zh-CN",
    "zh-TW", "zu",
  ]);
  const aliases = { ar: "ar-SA", ms: "ms-MY", no: "nb-NO", pt: "pt-PT", zh: "zh-CN" };

  function badgeLocale(language) {
    const normalized = String(language || "en").replace("_", "-");
    if (available.has(normalized)) return normalized;
    const lower = normalized.toLowerCase();
    if (lower === "pt-br") return "pt-BR";
    if (lower === "es-419") return "es-419";
    if (lower === "zh-tw" || lower === "zh-hk") return "zh-TW";
    const short = lower.split("-")[0];
    return aliases[short] || (available.has(short) ? short : "en");
  }

  function updateBadges(language) {
    const locale = badgeLocale(language || document.documentElement.lang || navigator.language);
    const source = `/assets/google-play-badges/${locale}.svg`;
    document.querySelectorAll("[data-google-play-badge]").forEach((image) => {
      image.src = source;
      image.lang = locale;
      image.alt = locale === "de" ? "Jetzt bei Google Play" : "Get it on Google Play";
    });
  }

  window.addEventListener("downloadthat:languagechange", (event) => updateBadges(event.detail.language));
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => updateBadges());
  } else {
    updateBadges();
  }
})();
