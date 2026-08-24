import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";

const root = new URL("..", import.meta.url);

test("foreground service demos are self-hosted and Pages-compatible", () => {
  const html = readFileSync(new URL("demo/index.html", root), "utf8");
  const dataSyncVideo = statSync(new URL("demo/downloadthat-foreground-service.mp4", root));
  const mediaPlaybackVideo = statSync(new URL("demo/downloadthat-media-playback-service.mp4", root));

  assert.ok(dataSyncVideo.size <= 25 * 1024 * 1024, "data sync video must fit the Cloudflare Pages single-asset limit");
  assert.ok(mediaPlaybackVideo.size <= 25 * 1024 * 1024, "media playback video must fit the Cloudflare Pages single-asset limit");
  assert.ok(mediaPlaybackVideo.size >= 100 * 1024, "media playback video must not be an empty placeholder");
  assert.match(html, /src="\/demo\/downloadthat-foreground-service\.mp4"/);
  assert.match(html, /src="\/demo\/downloadthat-media-playback-service\.mp4"/);
  assert.match(html, /user-initiated download/i);
  assert.match(html, /media notification/i);
  assert.doesNotMatch(html, /youtube|youtu\.be/i);
});
