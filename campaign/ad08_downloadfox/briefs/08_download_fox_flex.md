# Ad 08 — "Download Fox: Faster Than the Ad"

Fifth finished DownloadThat! campaign spot. New solo mascot, **Download Fox**
(orange fox, cyan brow/eye accents, black vest with a coral-to-teal gradient
download-arrow logo, hex-pattern tail) — a separate concept exploration from
ad07's Puzzle Dog, not a replacement. Energetic/confident direct-to-camera
personality, contrasting Puzzle Dog's dry deadpan.

Source: six user-supplied ChatGPT-generated stills (no human pairing or ad-
concept shots in this batch, unlike ad07's), copied to
`gAIstreich-comfy-agent/assets/downloadthat_ad_chatgpt_refs/` per Benjamin's
instruction, and organized here as the mascot reference set in
`refs/mascot/`. Same provenance treatment as ad07's mascot (see
`manifests/mascot.json` and DECISIONS.md ADR-017): externally-sourced stills,
locally-generated video.

No specific script/joke was given this time, so the concept below is this
session's creative call, kept simple given the leaner source material (one
character, no fake-ad-within-ad twist):

## Structure (~9-10s, 3 shots, mascot solo, no human)

1. **Intro** (~3s): Fox stands confidently on its neon stage, energetic
   greeting, slight head tilt, grin.
2. **Explainer** (~3s): Fox gestures while talking through the flow — paste
   link, pick video or audio.
3. **Phone reveal + tagline** (~3-4s): Fox raises its phone showing the real
   DownloadThat UI (composited, not the AI-drawn one), confident nod, closing
   line + brand tagline card.

## VO lines

1. "Still waiting for that ad to end?" — hyped, fast, rhetorical.
2. "Paste your link. Pick video or audio. Done." — punchy, three clean beats.
3. "DownloadThat. Way faster than watching an ad." — confident closer.

## Production standard (same recipe as ad07 — see that README for details)

- Video: LTX-2.3-22b-dev-fp8 + distilled-lora-384, 704x1280, 50fps,
  img_compression 0, single-reference-image i2v.
- Real screenshot composited into the phone-reveal frame, not hallucinated.
- Text overlay (tagline) via Pillow, not trusted to the image model.
