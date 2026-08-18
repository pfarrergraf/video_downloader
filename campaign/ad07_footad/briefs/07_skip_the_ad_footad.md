# Ad 07 — "Skip the ad" (fake foot-care commercial reveal)

Fourth finished concept in the DownloadThat! campaign (after AD1 spy/no-signup,
AD2 serial redownloader, AD3 notification hell). New human protagonist and a
new original mascot ("Puzzle Dog") are introduced here and locked for reuse in
future spots — see `manifests/main_character.json` and `manifests/mascot.json`.

## Joke structure

1. Cold open: absurd luxury foot-care commercial, extreme macro, no context.
2. Camera pulls back — it's playing on a phone, with a "Skip in 10" countdown.
3. The viewer (our protagonist) is annoyed: "I just wanna download that."
4. Mascot (Puzzle Dog) appears: "Easy. DownloadThat."
5. "How?" — mascot raises phone showing the real DownloadThat UI: "Like this."
6. Button: "Skip the ad. DownloadThat." / "Download video and audio."

## Ad copy — public-claims check

Checked against `security/PUBLIC_CLAIMS_POLICY.md` before any asset was
generated: no forbidden phrase present (no "any/all/most sites", no sideload
positioning, no "100% local" claim). "Download video and audio." and "Skip
the ad. DownloadThat." both match the canonical positioning. This is an
internal production asset — `market_my_app` profile still has
`release_status.public: false`; publishing (store, website, social) is a
separate later decision, not a production blocker.

## Production standard (matches this campaign's already-verified recipe)

- Reference stills: SDXL-Turbo, 384×704, 4 steps, cfg 1.0, euler_ancestral /
  sgm_uniform (native Turbo resolution — see `RESOLUTION_BUG_FIX.md`, do not
  use 720×1280 or similar).
- Video: LTX-2.3-22B-dev-fp8 + distilled-lora-384 (strength 0.5), 704×1280,
  **50 fps** (human micro-motion — see `EXPERIMENT_NOTES_i2v_settings.md`),
  `img_compression=0`, `prompt_enhancer` OFF (known Florence-2/transformers
  crash, not re-litigated here). Single reference-image i2v per shot (this
  campaign's proven pattern — not true first/last-frame interpolation, which
  has no verified graph in this install); the shot's *last* storyboard frame
  informs the motion-prompt wording, not a second conditioning image.
- Deliver at 1080×1920 (brief requirement) via LTX spatial upscaler already
  in this graph, not a separate step.
- Real brand assets reused instead of generated: `store_assets/icon-pro-1024.png`
  (dark navy rounded square, orange→teal→blue infinity/arrow mark) and
  `store_assets/screenshot_main.png` (magenta/crimson on off-white UI) —
  composited into frames 09/10, not hallucinated.
- Exact typography ("Skip in 10/9/8", "DownloadThat", tagline) composited
  with Pillow after generation, per campaign's own precedent (AD3 used
  `drawtext` overlays for the same reason — diffusion models can't render
  small legible text reliably).

## Mascot — "Puzzle Dog"

Small, knee-high, teal/cyan body with warm-yellow accents and visible
puzzle-piece seam lines, oversized eyes, floppy ears, dark nose, confident
dry-comic-timing personality (not childish/frantic). Palette bridges the
foot-ad's pink/magenta world and the real app's navy/orange-teal-blue icon
gradient — teal+cyan ties directly to the icon's cool end, yellow accent
echoes the icon's warm end.

## Human protagonist

New character, distinct from the existing spy-parody and redownloader leads
of AD1/AD2/AD3 (different concept, different look) — male, late 20s/early
30s, dark wavy hair, short stubble, blue-gray hoodie, mildly sarcastic,
believable-not-cartoonish. Locked reference sheet in `refs/character/`.

## Shotlist

| Shot | First frame | Motion | Duration | VO |
|---|---|---|---|---|
| A | 01 (macro ad) | slow hyper-premium push through the fake ad | ~3s | "Are you tired of having normal feet?" / "This may be the commercial you need." |
| B | 03→06 pull-out arc, rendered from 06 | rapid reveal: ad→phone→countdown→annoyed human | ~4s | "I just wanna download that." |
| C | 06→08 arc, rendered from 08 | mascot enters, two-shot | ~3s | Mascot: "Easy. DownloadThat." / Human: "How?" |
| D | 08→10 arc, rendered from 10 | mascot raises phone, app reveal | ~3-4s | Mascot: "Like this." / VO: "Skip the ad. DownloadThat." |

Given the single-reference-image i2v constraint above, each shot's *first*
column image is the actual LoadImage input; the "how it moves toward the next
beat" is carried entirely in the text prompt, matching AD1-3's own approach.
