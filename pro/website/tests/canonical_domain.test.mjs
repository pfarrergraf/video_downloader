import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/_middleware.js";

const next = async () => new Response("ok", { status: 200 });

test("canonical host responses receive HSTS", async () => {
  const response = await onRequest({
    request: new Request("https://downloadthat.app/download"),
    env: {},
    next,
  });
  assert.equal(response.status, 200);
  assert.match(response.headers.get("Strict-Transport-Security"), /includeSubDomains/);
});

test("www and pages.dev redirect only after the explicit migration switch", async () => {
  const env = {
    PUBLIC_BASE_URL: "https://downloadthat.app",
    CANONICAL_REDIRECT_ENABLED: "true",
  };
  for (const host of ["www.downloadthat.app", "downloadthat.pages.dev"]) {
    const response = await onRequest({
      request: new Request(`https://${host}/download/android?from=test`),
      env,
      next,
    });
    assert.equal(response.status, 308);
    assert.equal(response.headers.get("location"), "https://downloadthat.app/download/android?from=test");
  }
});

test("redirect remains disabled before custom-domain verification", async () => {
  const response = await onRequest({
    request: new Request("https://downloadthat.pages.dev/download"),
    env: { PUBLIC_BASE_URL: "https://downloadthat.app" },
    next,
  });
  assert.equal(response.status, 200);
});

test("non-idempotent API requests are never redirected", async () => {
  const response = await onRequest({
    request: new Request("https://downloadthat.pages.dev/api/play/rtdn", { method: "POST" }),
    env: { CANONICAL_REDIRECT_ENABLED: "true" },
    next,
  });
  assert.equal(response.status, 200);
});
