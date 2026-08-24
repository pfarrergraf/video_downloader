#!/usr/bin/env node
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const ROOTS = ["video_downloader/web/static/i18n", "pro/website/i18n"];

const EN = {
  status: "Free: {limit} successful downloads per rolling day. Pro removes DownloadThat's daily app download limit.",
  limit: "You've reached the Free allowance of {limit} successful downloads per rolling day. Pro removes DownloadThat's daily app download limit, or try again in {hours} hours.",
  lead: "Start free with 3 successful downloads per rolling 24 hours. Pro removes DownloadThat's daily app download limit.",
  feature: "No daily app download limit with Pro",
  faq: "No. Start free with 3 successful downloads per rolling 24 hours. Pro removes DownloadThat's daily app download limit.",
};
const DE = {
  status: "Kostenlos: {limit} erfolgreiche Downloads je rollierendem Tag. Pro entfernt das tägliche App-Downloadlimit von DownloadThat.",
  limit: "Du hast das kostenlose Kontingent von {limit} erfolgreichen Downloads je rollierendem Tag erreicht. Pro entfernt das tägliche App-Downloadlimit von DownloadThat. Oder versuche es in {hours} Stunden erneut.",
  lead: "Kostenlos starten mit 3 erfolgreichen Downloads je rollierenden 24 Stunden. Pro entfernt das tägliche App-Downloadlimit von DownloadThat.",
  feature: "Mit Pro kein tägliches App-Downloadlimit",
  faq: "Nein. Du startest kostenlos mit 3 erfolgreichen Downloads je rollierenden 24 Stunden. Pro entfernt das tägliche App-Downloadlimit von DownloadThat.",
};

export function normalizeClaims(document, locale) {
  const copy = locale === "de" ? DE : EN;
  if (document.app?.license) document.app.license.status_free = copy.status;
  if (document.app?.limit) document.app.limit.body = copy.limit;
  if (document.website?.pricing) {
    document.website.pricing.lead = copy.lead;
    document.website.pricing.feature_unlimited = copy.feature;
  }
  if (document.website?.faq) document.website.faq.q1_body = copy.faq;
  return document;
}

export function normalizeAllClaims(roots = ROOTS) {
  let changed = 0;
  for (const root of roots) {
    for (const name of readdirSync(root).filter((entry) => entry.endsWith(".json"))) {
      const path = join(root, name);
      const before = readFileSync(path, "utf8");
      const document = normalizeClaims(JSON.parse(before), name.replace(/\.json$/, ""));
      const after = `${JSON.stringify(document, null, 2)}\n`;
      if (after !== before) {
        writeFileSync(path, after, "utf8");
        changed += 1;
      }
    }
  }
  return changed;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(`Normalized public claims in ${normalizeAllClaims()} locale file(s).\n`);
}
