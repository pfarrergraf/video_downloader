# I2V settings experiment — concept 5 (spy portrait)

Date: 2026-08-12 · Model: LTX-2.3-22B-dev-fp8, 704×1280, 3s test clips, single seed,
source image `downloadthat_spy_portrait_v1.png`.

## What was tested
fps ∈ {25, 50} × prompt_enhancer ∈ {off, on}, everything else held constant
(`img_compression=0`, same prompt text, same LoRA/upscaler chain as the Luther
I2V template this was adapted from).

## Results

| Variant | Result | Runtime | Frames encoded | File size |
|---|---|---|---|---|
| fps 25, no enhancer | ✅ | 25.3s | 73 | 328 KB |
| fps 50, no enhancer | ✅ | 31.1s | 145 | 387 KB |
| fps 25, with enhancer | ❌ crashed | — | — | — |
| fps 50, with enhancer | ❌ crashed (same cause, not re-run) | — | — | — |

Clips + comparison frames: `campaign/raw/i2v_fps_experiment/`.

## Bug found: `prompt_enhancer` is currently broken
`LTXVPromptEnhancerLoader` unconditionally loads a Florence-2 image-captioner
(`MiaoshouAI/Florence-2-large-PromptGen-v2.0`) even when only the text-LLM half
is needed — the loader's `load()` calls `down_load_image_captioner()`
regardless of whether an `image_prompt` is later supplied to the enhancer node.
That model's HF remote code crashes on the currently-installed `transformers`
version:

```
AttributeError: 'Florence2LanguageConfig' object has no attribute 'forced_bos_token_id'
```

This is a known Florence-2/`transformers` version incompatibility, not a
mistake in the graph (both variants validated fine with `gai-comfy validate`
before running). Fixing it means pinning/patching a dependency shared by every
other LTX workflow in `gAIstreich-comfy-agent` — flagging it rather than
patching it silently, per that repo's own rule to check custom-node
dependency changes before making them. **Recommendation: leave
`prompt_enhancer` off until this is deliberately fixed at the comfy-agent
level**, not per-campaign.

## Recommendation for this campaign
Default to **50 fps** for shots with human micro-motion (blinks, grip
tightening, subtle head turns) — no visual defects introduced at 50 fps in
this test, and it matches what Luther's project already converged on for
similar reasons (their `AGENTS.md` documents a 24fps session that visibly
degraded lip-sync — same "more temporal resolution helps subtle motion"
lesson). The cost is real but small: +23% runtime, ~2x frame count/file size.
For shots with big/fast motion or static screen-recording inserts, 25fps is
probably fine and cheaper — worth a second, larger-motion test before locking
this as a blanket rule the way Luther did.

## Known issue carried over from the reference portrait — resolved
The original portrait (seed 1525176) had finger artifacts on the
phone-holding hand, visible in both video variants above. Rerolled with seed
3391847 → `campaign/refs/spy_character/spy_portrait_v1_final.png`, anatomically
coherent. The rejected original is kept at
`campaign/refs/spy_character/rejected/` for reference, not deleted. **The two
I2V clips in this experiment still show the old, bad-hand portrait** — they
were a settings test (fps/enhancer), not a final-asset run; re-run with the
new portrait before using either clip for anything beyond this comparison.
