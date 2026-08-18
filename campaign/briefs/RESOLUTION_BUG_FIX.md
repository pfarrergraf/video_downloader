# Resolution bug found and fixed (2026-08-12)

## The bug
All SDXL-Turbo portrait generations (`downloadthat_spy_*`, `downloadthat_redownloader_*`)
were rendered at 720×1280 or 768×1024. Checked the checkpoint's own embedded
safetensors metadata:

```
"modelspec.architecture": "stable-diffusion-xl-turbo-v1"
"modelspec.resolution": "512x512"
```

SDXL-Turbo was distilled (ADD) specifically at 512×512. 720×1280 has ~2.5x
the pixel area at a very different aspect ratio — well outside the
distillation target. This directly caused two artifacts already seen and
under-diagnosed in the earlier session: the double-exposure ghosting in
"shot4_hero" and the illegible/garbled phone-screen text in "shot2_hover".

LTX-2.3 (the video model) was not affected — its checkpoint carries no
resolution metadata, and 704×1280 was already the Luther team's own
empirically-validated standard (documented in comfy-agent's `AGENTS.md`),
which is what this campaign already used correctly.

## The fix
Switched all SDXL-Turbo portrait generation to **384×704** — same 9:16
aspect, ~270K px area vs. the native 262K (512×512), a 3% deviation instead
of the previous 251%. Confirmed by direct comparison: shot4's ghosting is
completely gone at the corrected resolution (before/after in
`campaign/raw/shot4_hero_00001_.png` vs `shot4_hero_fixed_res.png`).

The garbled UI text in shot2 improved (single phone instead of two, cleaner
composition) but text legibility itself is a separate, structural limit —
diffusion models cannot reliably render legible small text at any resolution.
That's why ad 3 ("Notification Hell") uses real `drawtext`-rendered popup
overlays composited on top of the AI plate, rather than expecting the model
to draw the popup text itself.

## What was regenerated after the fix
All 7 portraits and all 7 I2V clips (concepts 3 and 5) were regenerated at
the corrected resolution before being used in the final 3 ads. The two
`_00001_`-suffixed files under `campaign/raw/` predate the fix and are kept
only as the documented before/after comparison, not used in any final asset.

## Workflow files affected
`downloadthat_spy_portrait_v1.json`, `downloadthat_spy_shot{2,3,4}_*_v1.json`,
`downloadthat_redownloader_attempt{1,2,4}_*_v1.json` — all patched in place
(node "4", `EmptyLatentImage` width/height) in `gAIstreich-comfy-agent`. No
other project's workflow files were touched.
