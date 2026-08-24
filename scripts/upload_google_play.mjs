#!/usr/bin/env node
import { readFileSync, readdirSync } from "node:fs";
import { createSign, createPrivateKey } from "node:crypto";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const API = "https://androidpublisher.googleapis.com";
const TOKEN_URL = "https://oauth2.googleapis.com/token";
const SCOPE = "https://www.googleapis.com/auth/androidpublisher";

function base64url(value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value);
  return bytes.toString("base64url");
}

export function serviceAccountAssertion({ email, privateKey, nowSeconds = Math.floor(Date.now() / 1000) }) {
  const header = base64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims = base64url(JSON.stringify({
    iss: email,
    scope: SCOPE,
    aud: TOKEN_URL,
    iat: nowSeconds,
    exp: nowSeconds + 3600,
  }));
  const unsigned = `${header}.${claims}`;
  const signer = createSign("RSA-SHA256");
  signer.update(unsigned);
  signer.end();
  const normalizedKey = String(privateKey).replace(/\\n/g, "\n");
  const signature = signer.sign(createPrivateKey(normalizedKey));
  return `${unsigned}.${base64url(signature)}`;
}

async function responseJson(response, operation) {
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = body?.error?.message || `${response.status} ${response.statusText}`;
    const apiStatus = body?.error?.status ? `, ${body.error.status}` : "";
    const reason = body?.error?.details?.find((item) => item?.reason)?.reason;
    const apiReason = reason ? `, ${reason}` : "";
    throw new Error(`${operation} failed (${response.status}${apiStatus}${apiReason}): ${message}`);
  }
  return body;
}

async function publisherRequest(fetchImpl, url, options, operation) {
  return responseJson(await fetchImpl(url, options), operation);
}

export async function accessToken({ email, privateKey, fetchImpl = fetch, nowSeconds }) {
  const assertion = serviceAccountAssertion({ email, privateKey, nowSeconds });
  const response = await fetchImpl(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
  });
  const body = await responseJson(response, "OAuth token exchange");
  if (!body.access_token) throw new Error("OAuth token exchange returned no access token");
  return body.access_token;
}

export async function uploadGooglePlayBundle({
  packageName,
  track = "internal",
  releaseName,
  aabBytes,
  email,
  privateKey,
  fetchImpl = fetch,
  nowSeconds,
}) {
  if (track !== "internal") throw new Error("This release uploader is intentionally restricted to the internal track");
  const token = await accessToken({ email, privateKey, fetchImpl, nowSeconds });
  const headers = { Authorization: `Bearer ${token}` };
  const packagePath = encodeURIComponent(packageName);
  const edit = await responseJson(await fetchImpl(
    `${API}/androidpublisher/v3/applications/${packagePath}/edits`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}" },
  ), "Create Play edit");
  if (!edit.id) throw new Error("Create Play edit returned no edit id");
  const editPath = `${packagePath}/edits/${encodeURIComponent(edit.id)}`;
  const bundle = await responseJson(await fetchImpl(
    `${API}/upload/androidpublisher/v3/applications/${editPath}/bundles?uploadType=media`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/octet-stream" }, body: aabBytes },
  ), "Upload app bundle");
  if (!Number.isInteger(Number(bundle.versionCode))) throw new Error("Bundle upload returned no version code");
  const versionCode = String(bundle.versionCode);
  await responseJson(await fetchImpl(
    `${API}/androidpublisher/v3/applications/${editPath}/tracks/internal`,
    {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        track: "internal",
        releases: [{ name: releaseName, versionCodes: [versionCode], status: "completed" }],
      }),
    },
  ), "Update internal track");
  await responseJson(await fetchImpl(
    `${API}/androidpublisher/v3/applications/${editPath}:commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW`,
    { method: "POST", headers },
  ), "Commit Play edit");
  return { editId: edit.id, versionCode, track: "internal" };
}

/** Idempotently promote one already-verified candidate to Internal Testing.
 * A retry never uploads different bytes under another code: it either uploads
 * the expected code once, attaches an existing expected code to Internal, or
 * reports that the exact version is already present on the track. */
export async function promoteGooglePlayCandidate({
  packageName,
  releaseName,
  expectedVersionCode,
  aabBytes,
  email,
  privateKey,
  fetchImpl = fetch,
  nowSeconds,
}) {
  const expected = String(expectedVersionCode || "");
  if (!/^\d+$/.test(expected)) throw new Error("expectedVersionCode must be a positive integer");
  if (!/^candidate:[0-9a-f]{64}$/i.test(String(releaseName || ""))) {
    throw new Error("releaseName must bind the candidate SHA-256");
  }
  const token = await accessToken({ email, privateKey, fetchImpl, nowSeconds });
  const headers = { Authorization: `Bearer ${token}` };
  const packagePath = encodeURIComponent(packageName);
  const edit = await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${packagePath}/edits`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}" },
    "Create Play candidate edit",
  );
  if (!edit.id) throw new Error("Create Play candidate edit returned no edit id");
  const editPath = `${packagePath}/edits/${encodeURIComponent(edit.id)}`;
  let committed = false;
  try {
    const bundles = await publisherRequest(
      fetchImpl,
      `${API}/androidpublisher/v3/applications/${editPath}/bundles`,
      { headers },
      "List Play candidate bundles",
    );
    const bundleExists = (bundles.bundles || []).some((bundle) => String(bundle.versionCode) === expected);
    const track = await publisherRequest(
      fetchImpl,
      `${API}/androidpublisher/v3/applications/${editPath}/tracks/internal`,
      { headers },
      "Read internal track",
    );
    const matchingRelease = (track.releases || []).find((release) =>
      (release.versionCodes || []).map(String).includes(expected));
    if (bundleExists) {
      if (matchingRelease?.name === releaseName && matchingRelease?.status === "completed") {
        return { editId: edit.id, versionCode: expected, track: "internal", alreadyPresent: true };
      }
      throw new Error(
        `Play already knows versionCode ${expected} without the exact completed candidate binding`,
      );
    }
    if (matchingRelease) {
      throw new Error(`Internal track references versionCode ${expected} without a known bundle`);
    }
    const bundle = await publisherRequest(
      fetchImpl,
      `${API}/upload/androidpublisher/v3/applications/${editPath}/bundles?uploadType=media`,
      { method: "POST", headers: { ...headers, "Content-Type": "application/octet-stream" }, body: aabBytes },
      "Upload candidate app bundle",
    );
    if (String(bundle.versionCode) !== expected) {
      throw new Error(`Uploaded candidate versionCode ${bundle.versionCode} does not match expected ${expected}`);
    }
    await publisherRequest(
      fetchImpl,
      `${API}/androidpublisher/v3/applications/${editPath}/tracks/internal`,
      {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          track: "internal",
          releases: [{ name: releaseName, versionCodes: [expected], status: "completed" }],
        }),
      },
      "Update internal track with candidate",
    );
    await publisherRequest(
      fetchImpl,
      `${API}/androidpublisher/v3/applications/${editPath}:commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW`,
      { method: "POST", headers },
      "Commit Play candidate edit",
    );
    committed = true;
    return { editId: edit.id, versionCode: expected, track: "internal", alreadyPresent: false };
  } finally {
    if (!committed) {
      await publisherRequest(
        fetchImpl,
        `${API}/androidpublisher/v3/applications/${editPath}`,
        { method: "DELETE", headers },
        "Delete uncommitted Play candidate edit",
      );
    }
  }
}

/** Read the version codes already known to Google Play without committing an
 * edit. The temporary edit is deleted in all cases so a preflight check cannot
 * leave a competing edit behind. */
export async function highestGooglePlayVersionCode({
  packageName,
  email,
  privateKey,
  fetchImpl = fetch,
  nowSeconds,
}) {
  if (!packageName) throw new Error("packageName is required");
  const token = await accessToken({ email, privateKey, fetchImpl, nowSeconds });
  const headers = { Authorization: `Bearer ${token}` };
  const packagePath = encodeURIComponent(packageName);
  const edit = await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${packagePath}/edits`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}" },
    "Create Play version preflight edit",
  );
  if (!edit.id) throw new Error("Create Play version preflight edit returned no edit id");
  const editPath = `${packagePath}/edits/${encodeURIComponent(edit.id)}`;
  try {
    const response = await publisherRequest(
      fetchImpl,
      `${API}/androidpublisher/v3/applications/${editPath}/bundles`,
      { headers },
      "List Play app bundles",
    );
    const versionCodes = [...new Set((response.bundles || [])
      .map((bundle) => Number(bundle.versionCode))
      .filter(Number.isInteger))].sort((left, right) => left - right);
    return { highestVersionCode: versionCodes.at(-1) || 0, versionCodes };
  } finally {
    await publisherRequest(
      fetchImpl,
      `${API}/androidpublisher/v3/applications/${editPath}`,
      { method: "DELETE", headers },
      "Delete Play version preflight edit",
    );
  }
}

function featureGraphicForLanguage(assets, language) {
  const normalized = String(language).toLowerCase();
  if (normalized.startsWith("ja")) return assets.localizedFeatureGraphics?.ja || assets.featureGraphic;
  if (normalized.startsWith("ru")) return assets.localizedFeatureGraphics?.ru || assets.featureGraphic;
  if (normalized.startsWith("zh-cn") || normalized.startsWith("zh-hans")) {
    return assets.localizedFeatureGraphics?.["zh-CN"] || assets.featureGraphic;
  }
  return assets.featureGraphic;
}

export async function syncGooglePlayListingAssets({
  packageName,
  assets,
  email,
  privateKey,
  fetchImpl = fetch,
  nowSeconds,
  confirmUpload = false,
}) {
  if (!confirmUpload) throw new Error("Asset upload requires confirmUpload=true after dry-run review");
  if (!packageName) throw new Error("packageName is required");
  if (!assets?.featureGraphic || !assets?.phoneScreenshots?.length) {
    throw new Error("A feature graphic and at least one phone screenshot are required");
  }
  const token = await accessToken({ email, privateKey, fetchImpl, nowSeconds });
  const headers = { Authorization: `Bearer ${token}` };
  const packagePath = encodeURIComponent(packageName);
  const edit = await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${packagePath}/edits`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}" },
    "Create Play asset edit",
  );
  if (!edit.id) throw new Error("Create Play asset edit returned no edit id");
  const editPath = `${packagePath}/edits/${encodeURIComponent(edit.id)}`;
  const listingResponse = await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}/listings`,
    { headers },
    "List Play store listings",
  );
  const languages = [...new Set((listingResponse.listings || []).map((listing) => listing.language).filter(Boolean))];
  if (!languages.length) throw new Error("Google Play returned no store listing languages");

  const uploadImage = async (language, imageType, bytes, operation) => publisherRequest(
    fetchImpl,
    `${API}/upload/androidpublisher/v3/applications/${editPath}/listings/${encodeURIComponent(language)}/${imageType}?uploadType=media`,
    { method: "POST", headers: { ...headers, "Content-Type": "image/png" }, body: bytes },
    operation,
  );
  const deleteImages = async (language, imageType, operation) => publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}/listings/${encodeURIComponent(language)}/${imageType}`,
    { method: "DELETE", headers },
    operation,
  );

  for (const language of languages) {
    await deleteImages(language, "featureGraphic", `Delete old feature graphic (${language})`);
    await uploadImage(
      language,
      "featureGraphic",
      featureGraphicForLanguage(assets, language),
      `Upload feature graphic (${language})`,
    );
    await deleteImages(language, "phoneScreenshots", `Delete old phone screenshots (${language})`);
    for (const [index, screenshot] of assets.phoneScreenshots.entries()) {
      await uploadImage(
        language,
        "phoneScreenshots",
        screenshot,
        `Upload phone screenshot ${index + 1} (${language})`,
      );
    }
  }

  await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}:commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW`,
    { method: "POST", headers },
    "Commit Play asset edit",
  );
  return { editId: edit.id, languages, screenshotsPerLanguage: assets.phoneScreenshots.length };
}

// Separate from syncGooglePlayListingAssets above on purpose: that function
// broadcasts the same fixed screenshot set to every listing language, which
// is exactly the behavior below replaces for the home-screen shot without
// touching (or risking a regression in) the existing feature-graphic sync
// that function still owns.
//
// Google's own Play badge locale set (see pro/website/assets/store-badges.js,
// which this mirrors) is the closest thing this repo has to a validated list
// of language tags Play Console actually uses; the aliases below are the
// same ones already relied on there.
const PLAY_LANGUAGE_ALIASES = { ar: "ar-SA", ms: "ms-MY", no: "nb-NO", pt: "pt-PT", zh: "zh-CN" };

// Play Console still lists some languages under their old ISO 639-1 codes
// (pre-1989 Hebrew/Indonesian/Yiddish) instead of the modern ones our
// screenshot filenames use. Confirmed live: this app's own listing has
// "iw-IL", which resolved to the English fallback until this was added.
const LEGACY_SHORT_CODES = { iw: "he", in: "id", ji: "yi" };

/** Map a Play Console listing language (e.g. "de-DE", "zh-TW") to the
 * closest matching screenshot locale code (e.g. "de", "zh"), falling back
 * to "en" when nothing in `availableCodes` matches. Exported for testing. */
export function resolveScreenshotLocale(playLanguage, availableCodes) {
  const codes = new Set(availableCodes);
  const normalized = String(playLanguage || "en").replace("_", "-");
  const lower = normalized.toLowerCase();
  const short = LEGACY_SHORT_CODES[lower.split("-")[0]] || lower.split("-")[0];
  if (codes.has(short)) return short;
  const aliasHit = Object.entries(PLAY_LANGUAGE_ALIASES).find(([, tag]) => tag.toLowerCase() === lower);
  if (aliasHit && codes.has(aliasHit[0])) return aliasHit[0];
  return codes.has("en") ? "en" : [...codes][0];
}

/** Replace each listing language's phone screenshots with that language's
 * localized home-screen capture, light then dark — one real, distinct image
 * per language instead of the same English screenshots for every locale.
 * `screenshotsDir` must contain `screenshot_main_<code>.png` and
 * `screenshot_main_<code>_dark.png` for every code in `availableCodes`. */
export async function syncGooglePlayLocalizedScreenshots({
  packageName,
  screenshotsDir,
  availableCodes,
  email,
  privateKey,
  fetchImpl = fetch,
  nowSeconds,
  readFile = readFileSync,
  confirmUpload = false,
}) {
  if (!confirmUpload) throw new Error("Asset upload requires confirmUpload=true after dry-run review");
  if (!packageName) throw new Error("packageName is required");
  if (!screenshotsDir) throw new Error("screenshotsDir is required");
  if (!availableCodes?.length) throw new Error("availableCodes must list at least one screenshot locale code");

  const token = await accessToken({ email, privateKey, fetchImpl, nowSeconds });
  const headers = { Authorization: `Bearer ${token}` };
  const packagePath = encodeURIComponent(packageName);
  const edit = await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${packagePath}/edits`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}" },
    "Create Play locale-screenshot edit",
  );
  if (!edit.id) throw new Error("Create Play locale-screenshot edit returned no edit id");
  const editPath = `${packagePath}/edits/${encodeURIComponent(edit.id)}`;
  const listingResponse = await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}/listings`,
    { headers },
    "List Play store listings",
  );
  const languages = [...new Set((listingResponse.listings || []).map((listing) => listing.language).filter(Boolean))];
  if (!languages.length) throw new Error("Google Play returned no store listing languages");

  const uploadImage = async (language, bytes, operation) => publisherRequest(
    fetchImpl,
    `${API}/upload/androidpublisher/v3/applications/${editPath}/listings/${encodeURIComponent(language)}/phoneScreenshots?uploadType=media`,
    { method: "POST", headers: { ...headers, "Content-Type": "image/png" }, body: bytes },
    operation,
  );
  const deleteImages = async (language, operation) => publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}/listings/${encodeURIComponent(language)}/phoneScreenshots`,
    { method: "DELETE", headers },
    operation,
  );

  const perLanguageCode = {};
  for (const language of languages) {
    const code = resolveScreenshotLocale(language, availableCodes);
    perLanguageCode[language] = code;
    const light = readFile(`${screenshotsDir}/screenshot_main_${code}.png`);
    const dark = readFile(`${screenshotsDir}/screenshot_main_${code}_dark.png`);

    await deleteImages(language, `Delete old phone screenshots (${language})`);
    // Light before dark, per-language: two images, one theme demonstrated
    // each, not a broadcast copy of one locale's shots to every language.
    await uploadImage(language, light, `Upload light screenshot ${code} (${language})`);
    await uploadImage(language, dark, `Upload dark screenshot ${code} (${language})`);
  }

  await publisherRequest(
    fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}:commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW`,
    { method: "POST", headers },
    "Commit Play locale-screenshot edit",
  );
  return { editId: edit.id, languages, perLanguageCode };
}

export const PLAY_SCREENSHOT_CLASSES = Object.freeze([
  "phoneScreenshots",
  "sevenInchScreenshots",
  "tenInchScreenshots",
]);

/** Build a fully local, non-mutating upload plan for all Play screenshot slots.
 * Asset convention: <class-root>/<ui-locale>/*.png. Unsupported UI languages
 * resolve to the explicit `en` mapping in the canonical locale matrix. */
export function planGooglePlayScreenshotAssets({
  localeMatrix,
  assetDirectories,
  listFiles = readdirSync,
  minimumScreenshots = 4,
}) {
  const mappings = localeMatrix?.mappings || [];
  if (localeMatrix?.play_locale_count !== 86 || mappings.length !== 86) {
    throw new Error("Canonical locale matrix must contain exactly 86 Play locales");
  }
  if (localeMatrix?.ui_locale_count !== 50 || localeMatrix?.fallback_play_locale_count !== 20) {
    throw new Error("Canonical locale matrix must declare 50 UI locales and 20 English fallbacks");
  }
  const operations = [];
  const blockers = [];
  for (const imageType of PLAY_SCREENSHOT_CLASSES) {
    const root = assetDirectories?.[imageType];
    if (!root) {
      blockers.push(`${imageType}: asset directory is not configured`);
      continue;
    }
    const filesByUiLocale = new Map();
    for (const uiLocale of new Set(mappings.map((item) => item.ui_locale))) {
      const directory = join(root, uiLocale);
      let files = [];
      try {
        files = listFiles(directory).filter((name) => name.toLowerCase().endsWith(".png")).sort();
      } catch {
        blockers.push(`${imageType}/${uiLocale}: capture directory is missing`);
      }
      if (files.length < minimumScreenshots) {
        blockers.push(`${imageType}/${uiLocale}: requires at least ${minimumScreenshots} real PNG captures, found ${files.length}`);
      }
      filesByUiLocale.set(uiLocale, files.map((name) => join(directory, name)));
    }
    for (const mapping of mappings) {
      operations.push({
        playLocale: mapping.play_locale,
        uiLocale: mapping.ui_locale,
        mapping: mapping.mapping,
        imageType,
        files: filesByUiLocale.get(mapping.ui_locale) || [],
      });
    }
  }
  return {
    dryRun: true,
    playLocaleCount: mappings.length,
    assetClassCount: PLAY_SCREENSHOT_CLASSES.length,
    fallbackPlayLocaleCount: mappings.filter((item) => item.mapping === "fallback-en").length,
    operations,
    blockers: [...new Set(blockers)],
  };
}

/** Upload exactly a previously dry-runnable three-class screenshot layout.
 * Safe default is dry-run. A write additionally requires confirmUpload=true. */
export async function syncGooglePlayScreenshotAssets({
  packageName,
  localeMatrix,
  assetDirectories,
  dryRun = true,
  confirmUpload = false,
  email,
  privateKey,
  fetchImpl = fetch,
  nowSeconds,
  listFiles = readdirSync,
  readFile = readFileSync,
}) {
  if (!packageName) throw new Error("packageName is required");
  const plan = planGooglePlayScreenshotAssets({ localeMatrix, assetDirectories, listFiles });
  if (dryRun) return plan;
  if (!confirmUpload) throw new Error("A successful dry-run review and confirmUpload=true are required for asset upload");
  if (plan.blockers.length) throw new Error(`Screenshot asset plan is blocked: ${plan.blockers.join("; ")}`);
  if (!email || !privateKey) throw new Error("Google Play service-account secrets are not configured");

  const token = await accessToken({ email, privateKey, fetchImpl, nowSeconds });
  const headers = { Authorization: `Bearer ${token}` };
  const packagePath = encodeURIComponent(packageName);
  const edit = await publisherRequest(fetchImpl,
    `${API}/androidpublisher/v3/applications/${packagePath}/edits`,
    { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}" },
    "Create Play screenshot edit");
  if (!edit.id) throw new Error("Create Play screenshot edit returned no edit id");
  const editPath = `${packagePath}/edits/${encodeURIComponent(edit.id)}`;
  const listings = await publisherRequest(fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}/listings`, { headers }, "List Play store listings");
  const liveLanguages = [...new Set((listings.listings || []).map((item) => item.language).filter(Boolean))];
  const plannedLanguages = new Set(localeMatrix.mappings.map((item) => item.play_locale));
  const unmapped = liveLanguages.filter((language) => !plannedLanguages.has(language));
  if (unmapped.length) throw new Error(`Live Play locales missing from canonical matrix: ${unmapped.join(", ")}`);

  for (const operation of plan.operations.filter((item) => liveLanguages.includes(item.playLocale))) {
    const base = `${API}/androidpublisher/v3/applications/${editPath}/listings/${encodeURIComponent(operation.playLocale)}/${operation.imageType}`;
    await publisherRequest(fetchImpl, base, { method: "DELETE", headers },
      `Delete ${operation.imageType} (${operation.playLocale})`);
    for (const [index, file] of operation.files.entries()) {
      await publisherRequest(fetchImpl, `${API}/upload/androidpublisher/v3/applications/${editPath}/listings/${encodeURIComponent(operation.playLocale)}/${operation.imageType}?uploadType=media`,
        { method: "POST", headers: { ...headers, "Content-Type": "image/png" }, body: readFile(file) },
        `Upload ${operation.imageType} ${index + 1} (${operation.playLocale})`);
    }
  }
  await publisherRequest(fetchImpl,
    `${API}/androidpublisher/v3/applications/${editPath}:commit?changesInReviewBehavior=ERROR_IF_IN_REVIEW`,
    { method: "POST", headers }, "Commit Play screenshot edit");
  return { ...plan, dryRun: false, editId: edit.id, blockers: [] };
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    if (!key?.startsWith("--") || argv[index + 1] == null) throw new Error(`Invalid argument: ${key || "<missing>"}`);
    args[key.slice(2)] = argv[index + 1];
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args["sync-screenshot-assets"] === "true") {
    for (const required of ["package", "locale-matrix", "phone-dir", "seven-inch-dir", "ten-inch-dir"]) {
      if (!args[required]) throw new Error(`--${required} is required`);
    }
    const dryRun = args["dry-run"] !== "false";
    const result = await syncGooglePlayScreenshotAssets({
      packageName: args.package,
      localeMatrix: JSON.parse(readFileSync(args["locale-matrix"], "utf8")),
      assetDirectories: {
        phoneScreenshots: args["phone-dir"],
        sevenInchScreenshots: args["seven-inch-dir"],
        tenInchScreenshots: args["ten-inch-dir"],
      },
      dryRun,
      confirmUpload: args["confirm-upload"] === "true",
      email: process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL,
      privateKey: process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY,
    });
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }
  const legacyAssetMutation = args["sync-assets"] === "true" || args["sync-locale-screenshots"] === "true";
  if (legacyAssetMutation && args["dry-run"] !== "false") {
    process.stdout.write("Dry run: legacy asset sync was not executed. Use the three-class --sync-screenshot-assets planner.\n");
    return;
  }
  if (legacyAssetMutation && args["confirm-upload"] !== "true") {
    throw new Error("Asset upload requires --dry-run false --confirm-upload true");
  }
  const email = process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL;
  const privateKey = process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY;
  if (!email || !privateKey) throw new Error("Google Play service-account secrets are not configured");
  if (args["query-highest-version-code"] === "true") {
    if (!args.package) throw new Error("--package is required");
    const result = await highestGooglePlayVersionCode({
      packageName: args.package,
      email,
      privateKey,
    });
    process.stdout.write(`${JSON.stringify(result)}\n`);
    return;
  }
  if (args["sync-assets"] === "true") {
    if (!args.package || !args["asset-dir"]) throw new Error("--package and --asset-dir are required");
    const assetDir = args["asset-dir"];
    const result = await syncGooglePlayListingAssets({
      packageName: args.package,
      email,
      privateKey,
      assets: {
        featureGraphic: readFileSync(`${assetDir}/feature_graphic-1024x500.png`),
        localizedFeatureGraphics: {
          ja: readFileSync(`${assetDir}/feature_graphic-ja-1024x500.png`),
          ru: readFileSync(`${assetDir}/feature_graphic-ru-1024x500.png`),
          "zh-CN": readFileSync(`${assetDir}/feature_graphic-zh-CN-1024x500.png`),
        },
        phoneScreenshots: [
          readFileSync(`${assetDir}/screenshot_main.png`),
          readFileSync(`${assetDir}/screenshot_queue.png`),
          readFileSync(`${assetDir}/screenshot_settings.png`),
        ],
      },
      confirmUpload: true,
    });
    process.stdout.write(
      `Updated Play listing assets for ${result.languages.length} language(s): ${result.languages.join(", ")}\n`,
    );
    return;
  }
  if (args["sync-locale-screenshots"] === "true") {
    if (!args.package || !args["screenshots-dir"]) throw new Error("--package and --screenshots-dir are required");
    const screenshotsDir = args["screenshots-dir"];
    const availableCodes = [...new Set(
      readdirSync(screenshotsDir)
        .map((name) => name.match(/^screenshot_main_([a-z]+)(?:_dark)?\.png$/)?.[1])
        .filter(Boolean),
    )];
    const result = await syncGooglePlayLocalizedScreenshots({
      packageName: args.package,
      screenshotsDir,
      availableCodes,
      confirmUpload: true,
      email,
      privateKey,
    });
    process.stdout.write(
      `Updated localized phone screenshots for ${result.languages.length} language(s): `
        + `${result.languages.map((lang) => `${lang}->${result.perLanguageCode[lang]}`).join(", ")}\n`,
    );
    return;
  }
  for (const required of ["aab", "package", "release-name"]) {
    if (!args[required]) throw new Error(`--${required} is required`);
  }
  if (args["expected-version-code"]) {
    const result = await promoteGooglePlayCandidate({
      packageName: args.package,
      releaseName: args["release-name"],
      expectedVersionCode: args["expected-version-code"],
      aabBytes: readFileSync(args.aab),
      email,
      privateKey,
    });
    process.stdout.write(
      `${result.alreadyPresent ? "Verified existing" : "Promoted"} versionCode ${result.versionCode} `
        + `on Google Play ${result.track} track.\n`,
    );
    return;
  }
  const result = await uploadGooglePlayBundle({
    packageName: args.package,
    track: args.track || "internal",
    releaseName: args["release-name"],
    aabBytes: readFileSync(args.aab),
    email,
    privateKey,
  });
  process.stdout.write(`Uploaded versionCode ${result.versionCode} to Google Play ${result.track} track.\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
