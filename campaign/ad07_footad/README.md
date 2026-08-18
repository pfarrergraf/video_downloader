# Ad 07 — "Skip the ad" (fake foot-care commercial reveal)

Fourth finished DownloadThat! campaign spot (after AD1 spy/no-signup, AD2
serial redownloader, AD3 notification hell in `../selected/`). Introduces and
locks a new human protagonist and a new original mascot, **Puzzle Dog**, both
reusable in future spots.

## Result

`final/downloadthat_ad07_1080x1920.mp4` — 13.86s, 1080x1920, 50fps H.264 +
AAC, VO and music synced.

Also in `final/`: `downloadthat_ad07_master_704x1280.mp4` (pre-upscale
master), `downloadthat_ad07_no_audio.mp4`.

## Rerunning this build

```bash
python3 build_commercial.py validate   # check all inputs exist
python3 build_commercial.py compose    # Pillow text/UI overlay pass
python3 build_commercial.py assemble   # concat + VO/music mix + upscale
python3 build_commercial.py all        # both
```

Regenerating the reference stills, storyboard frames, VO, or video shots
themselves is an agentic ComfyUI loop, not a CLI step — see
`build_commercial.py`'s own docstring and
`../../../gAIstreich-comfy-agent/workflows/recipes/downloadthat_ad07_manifest.json`.

## What's locked for reuse in future spots

- **Human protagonist**: `refs/character/character_front.png` +
  `manifests/main_character.json` (exact prompt/seed/params).
- **Puzzle Dog mascot**: `refs/mascot/*.png` (front/3-4/side/back/happy/
  deadpan/phone-pose, cropped from the turnaround sheet) +
  `manifests/mascot.json`. **Note the provenance**: these stills came from a
  ChatGPT-generated sheet Benjamin supplied mid-session, not this repo's own
  ComfyUI — see the manifest for the full reasoning and the AGENTS.md
  reference-image-policy resolution in `gAIstreich-comfy-agent/DECISIONS.md`
  ADR-016.
- **Mascot voice**: `manifests/mascot_voice.json` (Qwen3-TTS CustomVoice,
  speaker `Uncle_Fu` — a first pick, not yet A/B-benchmarked like the Luther
  project's canonical voice).
- **Video recipe**: LTX-2.3-22b-dev-fp8 + distilled-lora, 704x1280, 50fps,
  single-reference-image i2v (no true first/last-frame interpolation graph
  verified on this install) — see the four
  `downloadthat_ad07_i2v_shot*_v1.json` files in comfy-agent's `workflows/api/`.

## Known limitations (don't silently re-attempt without reading this first)

- **No IP-Adapter/InstantID/PuLID/FaceID installed.** Multi-character scene
  composites (frames 07/08/09/10) use `TextEncodeQwenImageEditPlus` with two
  reference images instead — real, working, but not literal identity-locking;
  minor drift is visible and was accepted after review.
- **ACE-Step 1.5 music generation is broken** on this ComfyUI install: a
  tensor-dimension-mismatch crash inside the model's own `ace_step15.py`
  `prepare_condition`, not a parameter/graph-construction issue (both
  `validate_workflow` and the live `/prompt` validator pass first). Music/SFX
  here fall back to `../raw/music/` and `../raw/sfx/` stock assets from
  earlier concepts. Worth filing as a comfy-agent-level issue since it would
  block every future project's music generation, not just this one.
- **`LTXVPromptEnhancerLoader` remains broken** (documented Florence-2/
  `transformers` incompatibility, see
  `briefs/EXPERIMENT_NOTES_i2v_settings.md`) — left off.

## Before this goes anywhere public

`market_my_app` profile: `release_status.public: false`,
`allow_public_marketing: false`. This is a production asset for internal
review, not cleared to post. Also re-run
`security/PUBLIC_CLAIMS_POLICY.md`'s checklist against the final copy before
any public use — the ad copy here ("Download video and audio.", "Skip the ad.
DownloadThat.") was checked by hand during production and contains no
forbidden phrase, but the automated `scripts/check_public_claims.py` only
scans the public store/website paths, not campaign material, so it won't
catch this file on its own.
