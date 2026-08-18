# Ad 08 — "Download Fox: Faster Than the Ad"

Fifth finished DownloadThat! campaign spot. Solo-mascot direct-to-camera
product demo — no human pairing, no fake-ad twist, leaner than ad07 by
design (see `briefs/08_download_fox_flex.md` for why).

## Result

`final/downloadthat_ad08_1080x1920.mp4` — 9.2s, 1080x1920, 50fps H.264 + AAC.

Verified before delivery (lesson carried over from ad07's advisor review):
peak audio level −1.4 dB (no clipping), and the video was padded with a
held final frame (+0.6s) so the closing VO line isn't truncated by
`-shortest` — the raw shot concat was 0.4s shorter than the VO timeline
needed, which would have audibly cut off "...watching an ad."

## What's locked

- **Download Fox mascot**: `refs/mascot/*.png` (6 views, used directly as
  storyboard/video sources — see `manifests/mascot.json` for provenance).
  A **second, parallel** mascot alongside ad07's Puzzle Dog, not a
  replacement (DECISIONS.md ADR-017).
- **Voice**: Qwen3-TTS CustomVoice, speaker `Ryan` (energetic register,
  distinct from Puzzle Dog's `Uncle_Fu` and the ad07 announcer's `Vivian`).

## Known limitation

The rendered video's phone-reveal shot doesn't clearly show the phone screen
(motion carried it toward frame edge) — the real DownloadThat screenshot is
composited as a picture-in-picture overlay during the last 1.5s instead of
relying on the AI plate, same reasoning as every other UI moment in this
campaign (see `scripts/assemble_downloadthat_ad08.py`).

## Rerunning

No dedicated `build_commercial.py` yet for this ad (only 3 shots, simpler
pipeline) — rerun via:
```bash
python3 /home/benjamin_graf/projects/gAIstreich-comfy-agent/scripts/compose_downloadthat_ad08_overlays.py
python3 /home/benjamin_graf/projects/gAIstreich-comfy-agent/scripts/assemble_downloadthat_ad08.py
```
Video shots themselves require the ComfyUI agentic loop, same as ad07 — see
`workflows/api/downloadthat_ad08_i2v_shot*_v1.json` in comfy-agent.
