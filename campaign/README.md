# DownloadThat! app-ad campaign

Assets and tooling for AI-generated marketing images/videos promoting DownloadThat!
(this app). This folder is the project-specific half of a two-repo split with the
`gAIstreich-comfy-agent` repo, which owns the reusable ComfyUI plumbing running on
the WSL2/Ubuntu box.

## Split of responsibility

Corrected from an earlier wrong assumption (checked against a real template,
not guessed): comfy-agent does **not** hold generic reusable templates that
get parametrized elsewhere — every project there (Luther, "alltagsservice",
now this one) checks in its own **named, project-specific workflow graphs**,
prompt text baked in, e.g. `martin_luther_portrait_v1.json`,
`alltagsservice_garden_helper.json`. Ours follow the same convention with a
`downloadthat_` prefix.

- **`gAIstreich-comfy-agent`** (`~/projects/gAIstreich-comfy-agent` in WSL2) —
  the policy-gated ComfyUI CLI (`gai-comfy`) plus every project's workflow
  graphs under `workflows/{api,ui,recipes}/`, ours included
  (`downloadthat_*.json`). Read its `AGENTS.md` before touching it:
  local-runtime-only, no paid inference, no large models/media committed,
  quarantine instead of delete.
- **`campaign/` (here)** — everything that is *not* a ComfyUI graph: briefs,
  our own reference images, the resulting media, and a thin runner script
  that calls `gai-comfy run downloadthat_<name>` for shots already checked
  into comfy-agent and copies the result back.

## Layout

- `briefs/` — script ideas, hooks, shotlists (text, tracked in git)
- `refs/` — our own reference images/brand assets for image-to-video generation
  (small, tracked in git — never reuse another project's reference images)
- `scripts/build_graph.py` — loads a template from comfy-agent's `workflows/api/`,
  substitutes campaign-specific parameters, and runs it via `gai-comfy` over WSL
- `raw/` — every generated variant, **gitignored** — local disposable output
- `selected/` — the small number of finals promoted from `raw/`, **tracked in
  git** (same pattern as the existing `store_assets/` folder at the repo root)

## Why generation stays on WSL2-local disk

ComfyUI runs in WSL2 and writes its heavy per-frame I/O to a local scratch path
there, not directly across the `/mnt/c` boundary — cross-filesystem writes are
noticeably slower for video jobs. `build_graph.py` only crosses the boundary
twice per run: once to hand over the small materialized graph JSON, once to copy
back the finished output file(s) into `raw/`.

## Before anything goes public

Any new ad copy or visual claim must satisfy the existing project policy —
`docs/MARKETING_LEGAL_GUARDRAILS.md` and `security/PUBLIC_CLAIMS_POLICY.md` — and
pass `uv run python scripts/check_public_claims.py` before it ships anywhere
public (store listing, website, social post). In particular: no claims about
downloading from "any"/"all" sites, no third-party logos/brand colors as our own
imagery, no fabricated numbers or testimonials.
