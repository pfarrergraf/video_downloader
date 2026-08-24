import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { OBSERVED_PLAY_LOCALES, buildLocaleMatrix, uiLocalesFromDirectory } from "../scripts/build_play_locale_matrix.mjs";

test("canonical Play matrix is reproducible from actual UI locale files", () => {
  const stored = JSON.parse(readFileSync("store_assets/play_locale_matrix.json", "utf8"));
  const uiLocales = uiLocalesFromDirectory("video_downloader/web/static/i18n");
  assert.equal(uiLocales.length, 50);
  assert.equal(OBSERVED_PLAY_LOCALES.length, 86);
  assert.deepEqual(stored.mappings, buildLocaleMatrix(OBSERVED_PLAY_LOCALES, uiLocales));
  assert.equal(stored.fallback_play_locale_count, 20);
});

test("unsupported Play languages inherit English without claiming UI support", () => {
  const stored = JSON.parse(readFileSync("store_assets/play_locale_matrix.json", "utf8"));
  const unsupported = stored.mappings.filter((item) => !item.ui_supported);
  assert.equal(unsupported.length, 20);
  assert.ok(unsupported.every((item) => item.ui_locale === "en" && item.mapping === "fallback-en"));
  assert.deepEqual(unsupported.map((item) => item.play_locale), [
    "af", "sq", "hy-AM", "az-AZ", "eu-ES", "be", "my-MM", "ca", "gl-ES", "ka-GE",
    "is-IS", "kk", "km-KH", "ky-KG", "lo-LA", "mk-MK", "mn-MN", "ne-NP", "rm", "si-LK",
  ]);
});
