import test from "node:test";
import assert from "node:assert/strict";

import { createAffiliateSession } from "../functions/_affiliate.js";
import { onRequestPost } from "../functions/api/admin/retention-cleanup.js";
import { makeEnv } from "./helpers/fake-d1.mjs";

function cleanupRequest(headers = {}) {
  return new Request("https://downloadthat.pages.dev/api/admin/retention-cleanup", {
    method: "POST",
    headers,
  });
}

test("retention cleanup accepts the dedicated scheduler token", async () => {
  const env = makeEnv({ RETENTION_CLEANUP_TOKEN: "test-retention-token" });
  const response = await onRequestPost({
    request: cleanupRequest({ Authorization: "Bearer test-retention-token" }),
    env,
  });

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    ok: true,
    clicks_deleted: 0,
    activations_deleted: 0,
  });
});

test("retention cleanup rejects an invalid scheduler token", async () => {
  const env = makeEnv({ RETENTION_CLEANUP_TOKEN: "test-retention-token" });
  const response = await onRequestPost({
    request: cleanupRequest({ Authorization: "Bearer wrong-token" }),
    env,
  });

  assert.equal(response.status, 401);
  assert.deepEqual(await response.json(), { error: "unauthorized" });
});

test("retention cleanup preserves admin-session access", async () => {
  const env = makeEnv();
  const session = await createAffiliateSession(env, null, "admin");
  const response = await onRequestPost({
    request: cleanupRequest({ Cookie: `dt_partner_session=${session}` }),
    env,
  });

  assert.equal(response.status, 200);
  assert.equal((await response.json()).ok, true);
});
