import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url);
const read = (relative) => readFileSync(new URL(relative, root), "utf8");

test("homepage sends purchases to the Play-first Android page", () => {
  const html = read("index.html");
  assert.match(html, /id="buy-license-btn"[^>]+href="\/download\/android"/);
  assert.match(html, /data-google-play-badge/);
  assert.match(html, /data-play-store-link/);
  assert.match(html, /href="\/download"[^>]*>Alternative Downloads</);
  assert.doesNotMatch(html, /buy\.stripe\.com|data-stripe-link|withdrawal-modal/);
  assert.doesNotMatch(html, /No Play Store|No app store needed|no region locks/i);
});

test("production CSP does not permit inline scripts", () => {
  const headers = read("_headers");
  const htmlFiles = ["index.html", "widerruf.html"];
  assert.match(headers, /script-src 'self'/);
  assert.doesNotMatch(headers, /script-src[^;]*'unsafe-inline'/);
  for (const file of htmlFiles) {
    assert.doesNotMatch(read(file), /<script(?![^>]*\bsrc=)[^>]*>/i, file);
  }
});

test("download routes expose Play first, signed APK second, and planned iOS", () => {
  const landing = read("download/index.html");
  const android = read("download/android/index.html");
  const direct = read("download/direct/index.html");
  const ios = read("download/ios/index.html");

  assert.ok(landing.indexOf("Google Play") < landing.indexOf("signed APK"));
  assert.match(landing, /data-google-play-badge/);
  assert.match(landing, /Android Direct Installation \(APK\)/);
  assert.match(landing, /href="\/download\/windows"/);
  assert.match(landing, /iPhone &amp; iPad/);
  assert.match(android, /data-play-store-link/);
  assert.match(android, /data-google-play-badge/);
  assert.match(android, /href="\/download\/direct"/);
  assert.match(direct, /SHA-256 checksum/);
  assert.match(direct, /data-direct-apk-link/);
  assert.match(direct, /Pro cannot be purchased|no billing/i);
  assert.match(ios, /planned/i);
});

test("Play URL is configured centrally and fails closed while unset", () => {
  const config = read("functions/assets/runtime-config.js");
  const script = read("assets/download-pages.js");
  for (const page of ["download/index.html", "download/android/index.html", "download/direct/index.html"]) {
    assert.match(read(page), /src="\/assets\/runtime-config"/);
    assert.doesNotMatch(read(page), /runtime-config\.js/);
  }
  assert.match(config, /env\.PLAY_STORE_URL/);
  assert.match(config, /PLAY_STORE_URL:\s*playStoreUrl/);
  assert.match(script, /!playUrl\.includes\("__PLAY_STORE_URL__"\)/);
  assert.match(script, /aria-disabled/);
});

test("localized Google Play badges cover website languages with an explicit fallback", () => {
  const badges = new Set(readdirSync(new URL("assets/google-play-badges/", root)).filter((name) => name.endsWith(".svg")));
  const aliases = { ar: "ar-SA", ms: "ms-MY", no: "nb-NO", pt: "pt-PT", zh: "zh-CN" };
  for (const file of readdirSync(new URL("i18n/", root)).filter((name) => name.endsWith(".json"))) {
    const code = file.replace(/\.json$/, "");
    const badge = `${aliases[code] || code}.svg`;
    assert.ok(badges.has(badge) || code === "am", `${code} has no localized badge or documented English fallback`);
  }
  assert.match(read("assets/store-badges.js"), /return aliases\[short\].*"en"/s);
});

test("all locale files use store-neutral distribution copy", () => {
  for (const file of readdirSync(new URL("i18n/", root)).filter((name) => name.endsWith(".json"))) {
    const data = JSON.parse(read(join("i18n", file)));
    const activeCopy = [
      data.website.meta.description,
      data.website.hero.lead,
      data.website.features.f6_title,
      data.website.features.f6_desc,
      data.website.faq.q2_title,
      data.website.faq.q2_body,
      data.website.faq.q3_body,
      data.website.faq.q4_body,
    ].join(" ");
    assert.doesNotMatch(activeCopy, /no play store|kein play store|play store review|play-store-prüf|region locks|regionssperren/i, file);
  }
});

test("direct and Windows app purchase buttons explain Play license activation", () => {
  const html = read("../../video_downloader/web/static/index.html");
  assert.match(html, /downloadthat\.app\/download\/android/g);
  assert.equal((html.match(/data-i18n="app\.license\.purchase_hint"/g) || []).length, 2);
});
