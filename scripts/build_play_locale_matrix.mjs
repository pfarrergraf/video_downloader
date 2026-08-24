#!/usr/bin/env node
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const OBSERVED_PLAY_LOCALES = [
  "de-DE", "en-US", "fr-FR", "fr-CA", "es-ES", "it-IT", "nl-NL", "pl-PL", "zh-CN", "ja-JP", "ru-RU",
  "ar", "af", "sq", "am", "hy-AM", "az-AZ", "bn-BD", "eu-ES", "be", "bg", "my-MM", "ca", "zh-HK",
  "zh-TW", "hr", "cs-CZ", "da-DK", "en-AU", "en-CA", "en-GB", "en-IN", "en-SG", "en-ZA", "et", "fil",
  "fi-FI", "gl-ES", "ka-GE", "el-GR", "gu", "iw-IL", "hi-IN", "hu-HU", "is-IS", "id", "kn-IN", "kk",
  "km-KH", "ko-KR", "ky-KG", "lo-LA", "lv", "lt", "mk-MK", "ms-MY", "ms", "ml-IN", "mr-IN", "mn-MN",
  "ne-NP", "no-NO", "fa", "fa-AE", "fa-AF", "fa-IR", "pt-BR", "pt-PT", "pa", "ro", "rm", "sr", "si-LK",
  "sk", "sl", "es-419", "es-US", "sw", "sv-SE", "ta-IN", "te-IN", "th", "tr-TR", "uk", "ur", "vi",
];

const LEGACY = { iw: "he", in: "id", ji: "yi" };

export function uiLocalesFromDirectory(directory) {
  return readdirSync(directory)
    .map((name) => name.match(/^([a-z]+)\.json$/)?.[1])
    .filter(Boolean)
    .sort();
}

export function buildLocaleMatrix(playLocales, uiLocales) {
  const available = new Set(uiLocales);
  return playLocales.map((playLocale) => {
    const short = String(playLocale).toLowerCase().split("-")[0];
    const candidate = LEGACY[short] || short;
    const supported = available.has(candidate);
    return {
      play_locale: playLocale,
      ui_locale: supported ? candidate : "en",
      mapping: supported ? (playLocale.toLowerCase() === candidate ? "exact" : "base-language") : "fallback-en",
      ui_supported: supported,
    };
  });
}

export function writeCanonicalMatrix({
  uiDirectory = "video_downloader/web/static/i18n",
  output = "store_assets/play_locale_matrix.json",
} = {}) {
  const uiLocales = uiLocalesFromDirectory(uiDirectory);
  const mappings = buildLocaleMatrix(OBSERVED_PLAY_LOCALES, uiLocales);
  const document = {
    schema_version: 1,
    source: {
      kind: "live-play-listings",
      github_actions_run: 32484439312,
      observed_at: "2026-08-21T13:11:06Z",
    },
    default_ui_locale: "en",
    ui_locale_count: uiLocales.length,
    play_locale_count: mappings.length,
    fallback_play_locale_count: mappings.filter((item) => !item.ui_supported).length,
    ui_locales: uiLocales,
    mappings,
  };
  writeFileSync(output, `${JSON.stringify(document, null, 2)}\n`, "utf8");
  return document;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const result = writeCanonicalMatrix();
  process.stdout.write(
    `Wrote ${result.play_locale_count} Play locales: ${result.ui_locale_count} UI locales, `
      + `${result.fallback_play_locale_count} English fallbacks.\n`,
  );
}
