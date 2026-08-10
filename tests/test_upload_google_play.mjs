import assert from "node:assert/strict";
import test from "node:test";
import { generateKeyPairSync } from "node:crypto";
import { serviceAccountAssertion, uploadGooglePlayBundle } from "../scripts/upload_google_play.mjs";

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
