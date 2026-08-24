import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { FREE_MARKER, PRO_LIMIT, ROLLING_FREE } from "../scripts/normalize_public_claims.mjs";

const ROOTS = ["video_downloader/web/static/i18n", "pro/website/i18n"];

test("all 50 real UI locales use their exact qualified rolling-quota claim map", () => {
  assert.equal(Object.keys(PRO_LIMIT).length, 50);
  assert.deepEqual(Object.keys(PRO_LIMIT).sort(), Object.keys(ROLLING_FREE).sort());
  assert.deepEqual(Object.keys(PRO_LIMIT).sort(), Object.keys(FREE_MARKER).sort());
  for (const root of ROOTS) {
    const locales = readdirSync(root).filter((name) => name.endsWith(".json")).map((name) => name.slice(0, -5)).sort();
    assert.deepEqual(locales, Object.keys(PRO_LIMIT).sort());
    for (const locale of locales) {
      const document = JSON.parse(readFileSync(join(root, `${locale}.json`), "utf8"));
      const quota = (count) => ROLLING_FREE[locale].replace("{count}", count);
      assert.ok(ROLLING_FREE[locale].includes(FREE_MARKER[locale]), `${locale} lost its localized free marker`);
      assert.equal(document.app.license.status_free, `${quota("{limit}")}. ${PRO_LIMIT[locale]}`);
      assert.equal(document.app.limit.body, `${quota("{limit}")}. ${PRO_LIMIT[locale]} ({hours} h).`);
      assert.equal(document.website.pricing.lead, `${quota("3")}. ${PRO_LIMIT[locale]}`);
      assert.equal(document.website.pricing.feature_unlimited, PRO_LIMIT[locale]);
      assert.equal(document.website.faq.q1_body, `${quota("3")}. ${PRO_LIMIT[locale]}`);
    }
  }
});

test("supported non-English UI locales never receive the English claim copy", () => {
  const english = JSON.parse(readFileSync(`${ROOTS[0]}/en.json`, "utf8"));
  const englishValues = [
    english.app.license.status_free,
    english.app.limit.body,
    english.website.pricing.lead,
    english.website.pricing.feature_unlimited,
    english.website.faq.q1_body,
  ];
  for (const name of readdirSync(ROOTS[0]).filter((entry) => entry.endsWith(".json") && entry !== "en.json")) {
    const value = JSON.parse(readFileSync(join(ROOTS[0], name), "utf8"));
    const localized = [value.app.license.status_free, value.app.limit.body, value.website.pricing.lead,
      value.website.pricing.feature_unlimited, value.website.faq.q1_body];
    assert.ok(localized.every((item, index) => item !== englishValues[index]), `${name} reused English claim copy`);
  }
});
