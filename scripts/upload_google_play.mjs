#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { createSign, createPrivateKey } from "node:crypto";
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
  for (const required of ["aab", "package", "release-name"]) {
    if (!args[required]) throw new Error(`--${required} is required`);
  }
  const email = process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL;
  const privateKey = process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY;
  if (!email || !privateKey) throw new Error("Google Play service-account secrets are not configured");
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
