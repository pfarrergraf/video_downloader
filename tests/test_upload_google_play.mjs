import assert from "node:assert/strict";
import test from "node:test";
import { generateKeyPairSync } from "node:crypto";
import { readFileSync } from "node:fs";
import {
  highestGooglePlayVersionCode,
  planGooglePlayScreenshotAssets,
  promoteGooglePlayCandidate,
  resolveScreenshotLocale,
  serviceAccountAssertion,
  syncGooglePlayListingAssets,
  syncGooglePlayLocalizedScreenshots,
  syncGooglePlayScreenshotAssets,
  uploadGooglePlayBundle,
} from "../scripts/upload_google_play.mjs";

const { privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const PEM = privateKey.export({ type: "pkcs8", format: "pem" });

test("service-account assertion uses the Android Publisher scope", () => {
  const jwt = serviceAccountAssertion({ email: "ci@example.test", privateKey: PEM, nowSeconds: 1234 });
  const [, payload] = jwt.split(".");
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  assert.equal(claims.iss, "ci@example.test");
  assert.equal(claims.scope, "https://www.googleapis.com/auth/androidpublisher");
  assert.equal(claims.exp - claims.iat, 3600);
});

test("uploader creates an edit, uploads AAB, updates internal track and commits safely", async () => {
  const calls = [];
  const responses = [
    { access_token: "token" },
    { id: "edit-1" },
    { versionCode: 100000 },
    { track: "internal" },
    { id: "edit-1" },
  ];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return Response.json(responses.shift());
  };
  const result = await uploadGooglePlayBundle({
    packageName: "de.classydl.app",
    releaseName: "v1.0.0",
    aabBytes: Buffer.from("aab"),
    email: "ci@example.test",
    privateKey: PEM,
    fetchImpl,
    nowSeconds: 1234,
  });
  assert.deepEqual(result, { editId: "edit-1", versionCode: "100000", track: "internal" });
  assert.match(calls[2].url, /\/upload\/androidpublisher\/v3\/applications\/de.classydl.app\/edits\/edit-1\/bundles\?uploadType=media$/);
  assert.equal(calls[2].options.headers["Content-Type"], "application/octet-stream");
  const trackBody = JSON.parse(calls[3].options.body);
  assert.deepEqual(trackBody.releases[0].versionCodes, ["100000"]);
  assert.equal(trackBody.releases[0].status, "completed");
  assert.match(calls[4].url, /:commit\?changesInReviewBehavior=ERROR_IF_IN_REVIEW$/);
});

test("uploader refuses any non-internal track", async () => {
  await assert.rejects(
    () => uploadGooglePlayBundle({ track: "production" }),
    /restricted to the internal track/,
  );
});

test("uploader preserves Google API status and reason in failures", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) return Response.json({ access_token: "token" });
    return Response.json(
      {
        error: {
          message: "The caller does not have permission",
          status: "PERMISSION_DENIED",
          details: [{ reason: "PLAY_CONSOLE_PERMISSION" }],
        },
      },
      { status: 403 },
    );
  };
  await assert.rejects(
    () => uploadGooglePlayBundle({
      packageName: "de.classydl.app",
      releaseName: "v1.0.0",
      aabBytes: Buffer.from("aab"),
      email: "ci@example.test",
      privateKey: PEM,
      fetchImpl,
      nowSeconds: 1234,
    }),
    /Create Play edit failed \(403, PERMISSION_DENIED, PLAY_CONSOLE_PERMISSION\)/,
  );
});

test("version preflight returns the highest Play code and deletes its temporary edit", async () => {
  const calls = [];
  const responses = [
    { access_token: "token" },
    { id: "edit-versions" },
    { bundles: [{ versionCode: 80403 }, { versionCode: "1000401" }, { versionCode: 80500 }] },
    {},
  ];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return Response.json(responses.shift());
  };
  const result = await highestGooglePlayVersionCode({
    packageName: "de.classydl.app",
    email: "ci@example.test",
    privateKey: PEM,
    fetchImpl,
    nowSeconds: 1234,
  });
  assert.deepEqual(result, {
    highestVersionCode: 1000401,
    versionCodes: [80403, 80500, 1000401],
  });
  assert.match(calls[2].url, /\/edits\/edit-versions\/bundles$/);
  assert.equal(calls[3].options.method, "DELETE");
  assert.match(calls[3].url, /\/edits\/edit-versions$/);
});

test("candidate promotion uploads only the expected version and commits Internal", async () => {
  const binding = `candidate:${"a".repeat(64)}`;
  const calls = [];
  const responses = [
    { access_token: "token" },
    { id: "edit-candidate" },
    { bundles: [{ versionCode: 1000401 }] },
    { track: "internal", releases: [] },
    { versionCode: 1000402 },
    { track: "internal" },
    { id: "edit-candidate" },
  ];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return Response.json(responses.shift());
  };
  const result = await promoteGooglePlayCandidate({
    packageName: "de.classydl.app",
    releaseName: binding,
    expectedVersionCode: 1000402,
    aabBytes: Buffer.from("candidate"),
    email: "ci@example.test",
    privateKey: PEM,
    fetchImpl,
    nowSeconds: 1234,
  });
  assert.deepEqual(result, {
    editId: "edit-candidate",
    versionCode: "1000402",
    track: "internal",
    alreadyPresent: false,
  });
  assert.equal(calls.filter((call) => call.url.includes("upload/androidpublisher")).length, 1);
  assert.match(calls.at(-1).url, /:commit\?changesInReviewBehavior=ERROR_IF_IN_REVIEW$/);
});

test("candidate promotion retry reuses a version already on Internal without uploading", async () => {
  const binding = `candidate:${"b".repeat(64)}`;
  const calls = [];
  const responses = [
    { access_token: "token" },
    { id: "edit-retry" },
    { bundles: [{ versionCode: 1000402 }] },
    { track: "internal", releases: [{ name: binding, status: "completed", versionCodes: ["1000402"] }] },
    {},
  ];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return Response.json(responses.shift());
  };
  const result = await promoteGooglePlayCandidate({
    packageName: "de.classydl.app",
    releaseName: binding,
    expectedVersionCode: 1000402,
    aabBytes: Buffer.from("candidate"),
    email: "ci@example.test",
    privateKey: PEM,
    fetchImpl,
    nowSeconds: 1234,
  });
  assert.equal(result.alreadyPresent, true);
  assert.equal(calls.some((call) => call.url.includes("upload/androidpublisher")), false);
  assert.equal(calls.at(-1).options.method, "DELETE");
});

test("candidate promotion fails closed for an existing unbound version", async () => {
  const calls = [];
  const responses = [
    { access_token: "token" },
    { id: "edit-conflict" },
    { bundles: [{ versionCode: 1000402 }] },
    { track: "internal", releases: [{ name: "manual", status: "completed", versionCodes: ["1000402"] }] },
    {},
  ];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return Response.json(responses.shift());
  };
  await assert.rejects(
    promoteGooglePlayCandidate({
      packageName: "de.classydl.app",
      releaseName: `candidate:${"c".repeat(64)}`,
      expectedVersionCode: 1000402,
      aabBytes: Buffer.from("candidate"),
      email: "ci@example.test",
      privateKey: PEM,
      fetchImpl,
      nowSeconds: 1234,
    }),
    /without the exact completed candidate binding/,
  );
  assert.equal(calls.some((call) => call.url.includes("upload/androidpublisher")), false);
  assert.equal(calls.at(-1).options.method, "DELETE");
});

test("asset sync replaces graphics for every existing listing language and commits safely", async () => {
  const calls = [];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (calls.length === 1) return Response.json({ access_token: "token" });
    if (calls.length === 2) return Response.json({ id: "edit-assets" });
    if (calls.length === 3) {
      return Response.json({ listings: [{ language: "de-DE" }, { language: "ja-JP" }] });
    }
    return Response.json({ image: { id: `image-${calls.length}` } });
  };
  const result = await syncGooglePlayListingAssets({
    packageName: "de.classydl.app",
    email: "ci@example.test",
    privateKey: PEM,
    fetchImpl,
    nowSeconds: 1234,
    confirmUpload: true,
    assets: {
      featureGraphic: Buffer.from("generic-feature"),
      localizedFeatureGraphics: { ja: Buffer.from("japanese-feature") },
      phoneScreenshots: [Buffer.from("main"), Buffer.from("queue"), Buffer.from("settings")],
    },
  });

  assert.deepEqual(result, {
    editId: "edit-assets",
    languages: ["de-DE", "ja-JP"],
    screenshotsPerLanguage: 3,
  });
  assert.equal(calls.filter((call) => call.options.method === "DELETE").length, 4);
  const featureUploads = calls.filter((call) => call.url.includes("/featureGraphic?uploadType=media"));
  assert.equal(featureUploads.length, 2);
  assert.equal(featureUploads[0].options.body.toString(), "generic-feature");
  assert.equal(featureUploads[1].options.body.toString(), "japanese-feature");
  assert.equal(calls.filter((call) => call.url.includes("/phoneScreenshots?uploadType=media")).length, 6);
  assert.match(calls.at(-1).url, /:commit\?changesInReviewBehavior=ERROR_IF_IN_REVIEW$/);
});

test("resolveScreenshotLocale prefers an exact code, then a known Play alias, then falls back to en", () => {
  const codes = ["en", "de", "fr", "pt", "zh", "ar"];
  assert.equal(resolveScreenshotLocale("de-DE", codes), "de");
  assert.equal(resolveScreenshotLocale("pt-PT", codes), "pt");
  assert.equal(resolveScreenshotLocale("zh-TW", codes), "zh");
  assert.equal(resolveScreenshotLocale("ar-SA", codes), "ar");
  assert.equal(resolveScreenshotLocale("nb-NO", ["en", "no"]), "no");
  assert.equal(resolveScreenshotLocale("xx-XX", codes), "en");
});

test("resolveScreenshotLocale maps legacy ISO codes Play Console still lists (iw, in) to the modern code", () => {
  // Confirmed live on this app's actual Play listing: "iw-IL" (Hebrew's old
  // code) was falling back to English before this was handled.
  assert.equal(resolveScreenshotLocale("iw-IL", ["en", "he"]), "he");
  assert.equal(resolveScreenshotLocale("in", ["en", "id"]), "id");
});

test("three-class screenshot plan covers 86 locales and preserves explicit English fallbacks", () => {
  const localeMatrix = JSON.parse(readFileSync("store_assets/play_locale_matrix.json", "utf8"));
  const plan = planGooglePlayScreenshotAssets({
    localeMatrix,
    assetDirectories: {
      phoneScreenshots: "captures/phone",
      sevenInchScreenshots: "captures/7-inch",
      tenInchScreenshots: "captures/10-inch",
    },
    listFiles: () => ["01.png", "02.png", "03.png", "04.png"],
  });
  assert.equal(plan.dryRun, true);
  assert.equal(plan.playLocaleCount, 86);
  assert.equal(plan.assetClassCount, 3);
  assert.equal(plan.fallbackPlayLocaleCount, 20);
  assert.equal(plan.operations.length, 86 * 3);
  assert.deepEqual(plan.blockers, []);
  assert.equal(plan.operations.find((item) => item.playLocale === "af").uiLocale, "en");
  assert.deepEqual(new Set(plan.operations.map((item) => item.imageType)), new Set([
    "phoneScreenshots", "sevenInchScreenshots", "tenInchScreenshots",
  ]));
});

test("screenshot sync is a network-free dry-run by default", async () => {
  const localeMatrix = JSON.parse(readFileSync("store_assets/play_locale_matrix.json", "utf8"));
  let networkCalls = 0;
  const result = await syncGooglePlayScreenshotAssets({
    packageName: "de.classydl.app",
    localeMatrix,
    assetDirectories: {
      phoneScreenshots: "captures/phone",
      sevenInchScreenshots: "captures/7-inch",
      tenInchScreenshots: "captures/10-inch",
    },
    listFiles: () => ["01.png", "02.png", "03.png", "04.png"],
    fetchImpl: async () => { networkCalls += 1; throw new Error("must not run"); },
  });
  assert.equal(result.dryRun, true);
  assert.equal(networkCalls, 0);
});

test("missing real tablet captures block an upload plan", () => {
  const localeMatrix = JSON.parse(readFileSync("store_assets/play_locale_matrix.json", "utf8"));
  const plan = planGooglePlayScreenshotAssets({
    localeMatrix,
    assetDirectories: {
      phoneScreenshots: "captures/phone",
      sevenInchScreenshots: "captures/7-inch",
      tenInchScreenshots: "captures/10-inch",
    },
    listFiles: (directory) => directory.includes("phone") ? ["01.png", "02.png", "03.png", "04.png"] : [],
  });
  assert.ok(plan.blockers.some((item) => item.startsWith("sevenInchScreenshots/")));
  assert.ok(plan.blockers.some((item) => item.startsWith("tenInchScreenshots/")));
});

test("legacy asset writers also fail closed without explicit confirmation", async () => {
  let networkCalls = 0;
  await assert.rejects(
    syncGooglePlayListingAssets({
      packageName: "de.classydl.app",
      assets: { featureGraphic: Buffer.from("feature"), phoneScreenshots: [Buffer.from("phone")] },
      fetchImpl: async () => { networkCalls += 1; throw new Error("must not run"); },
    }),
    /confirmUpload=true/,
  );
  assert.equal(networkCalls, 0);
});

test("locale-screenshot sync uploads each language's own light+dark shot, not a shared broadcast set", async () => {
  const files = {
    "screenshots/screenshot_main_en.png": Buffer.from("en-light"),
    "screenshots/screenshot_main_en_dark.png": Buffer.from("en-dark"),
    "screenshots/screenshot_main_de.png": Buffer.from("de-light"),
    "screenshots/screenshot_main_de_dark.png": Buffer.from("de-dark"),
  };
  const readFile = (path) => {
    if (!(path in files)) throw new Error(`unexpected read: ${path}`);
    return files[path];
  };
  const calls = [];
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (calls.length === 1) return Response.json({ access_token: "token" });
    if (calls.length === 2) return Response.json({ id: "edit-locale" });
    if (calls.length === 3) {
      // ja-JP has no matching screenshot code and must fall back to "en".
      return Response.json({ listings: [{ language: "de-DE" }, { language: "ja-JP" }] });
    }
    return Response.json({ image: { id: `image-${calls.length}` } });
  };

  const result = await syncGooglePlayLocalizedScreenshots({
    packageName: "de.classydl.app",
    screenshotsDir: "screenshots",
    availableCodes: ["en", "de"],
    email: "ci@example.test",
    privateKey: PEM,
    fetchImpl,
    nowSeconds: 1234,
    readFile,
    confirmUpload: true,
  });

  assert.deepEqual(result, {
    editId: "edit-locale",
    languages: ["de-DE", "ja-JP"],
    perLanguageCode: { "de-DE": "de", "ja-JP": "en" },
  });
  const deletes = calls.filter((call) => call.options.method === "DELETE");
  assert.equal(deletes.length, 2);
  const uploads = calls.filter((call) => call.url.includes("/phoneScreenshots?uploadType=media"));
  assert.equal(uploads.length, 4);
  // de-DE gets its own German shots, light before dark; ja-JP falls back to English.
  assert.equal(uploads[0].url.includes("/listings/de-DE/"), true);
  assert.equal(uploads[0].options.body.toString(), "de-light");
  assert.equal(uploads[1].url.includes("/listings/de-DE/"), true);
  assert.equal(uploads[1].options.body.toString(), "de-dark");
  assert.equal(uploads[2].url.includes("/listings/ja-JP/"), true);
  assert.equal(uploads[2].options.body.toString(), "en-light");
  assert.equal(uploads[3].options.body.toString(), "en-dark");
  assert.match(calls.at(-1).url, /:commit\?changesInReviewBehavior=ERROR_IF_IN_REVIEW$/);
});
