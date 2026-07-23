import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";

const root = new URL("..", import.meta.url);

test("foreground service demo is self-hosted and Pages-compatible", () => {
  const html = readFileSync(new URL("demo/index.html", root), "utf8");
  const video = statSync(new URL("demo/downloadthat-foreground-service.mp4", root));

  assert.ok(video.size <= 25 * 1024 * 1024, "video must fit the Cloudflare Pages single-asset limit");
  assert.match(html, /src="\/demo\/downloadthat-foreground-service\.mp4"/);
  assert.match(html, /user-initiated download/i);
  assert.doesNotMatch(html, /youtube|youtu\.be/i);
});
