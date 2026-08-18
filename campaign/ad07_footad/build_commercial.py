#!/usr/bin/env python3
"""Reusable orchestration entry point for the ad07 'Skip the ad' commercial
(and the template for future DownloadThat! spots reusing the same locked
character/mascot).

What this script automates end-to-end (deterministic, no model inference):
    validate  -- check that every required input asset exists
    compose   -- Pillow text/UI overlay pass over clean storyboard frames
    assemble  -- concat shots, build the VO+music timeline, mux, upscale

What it does NOT automate, and why: generating/regenerating the character
and mascot reference stills, the storyboard keyframes, the VO lines, and the
LTX-2.3 video shots all require a running ComfyUI instance driven through
the mcp__comfyui__* tool surface (enqueue -> poll -> inspect -> reroll on a
failed quality gate) -- that loop is inherently agentic (see brief section
25: "if a step fails, inspect the actual error, determine the smallest fix,
retry"), not a fire-and-forget CLI call. The exact graphs used are checked
into gAIstreich-comfy-agent under workflows/api/downloadthat_ad07_*.json and
workflows/recipes/downloadthat_ad07_manifest.json; re-run them the same way
this session did (mcp__comfyui__enqueue_workflow with the LoadImage/prompt
swapped, or `gai-comfy run` per campaign/README.md's existing convention).

Usage:
    python build_commercial.py validate
    python build_commercial.py compose
    python build_commercial.py assemble
    python build_commercial.py all          # compose + assemble
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CAMP = Path(__file__).resolve().parent
COMFY_AGENT = Path("/home/benjamin_graf/projects/gAIstreich-comfy-agent")

REQUIRED = [
    CAMP / "refs" / "character" / "character_front.png",
    CAMP / "refs" / "mascot" / "mascot_front.png",
    CAMP / "refs" / "mascot" / "mascot_phone_pose.png",
    CAMP / "refs" / "brand" / "screenshot_main.jpeg",
    CAMP / "refs" / "brand" / "icon_real.png",
    *[CAMP / "storyboard" / "clean" / f"{i:02d}.png" for i in range(1, 11)],
    *[CAMP / "audio" / "vo" / name for name in [
        "01a_tired_of_feet.wav", "01b_commercial_you_need.wav",
        "02_human_downloadthat.wav", "03_mascot_easy.wav",
        "04_human_how.wav", "05_mascot_like_this.wav", "06_final_vo.wav",
    ]],
]


def validate() -> bool:
    missing = [p for p in REQUIRED if not p.exists()]
    for p in missing:
        print(f"MISSING: {p}")
    if missing:
        print(f"\n{len(missing)} required input(s) missing -- regenerate via ComfyUI "
              f"(see workflows/recipes/downloadthat_ad07_manifest.json) before compose/assemble.")
        return False
    print(f"All {len(REQUIRED)} required inputs present.")
    return True


def compose():
    subprocess.run([sys.executable, str(COMFY_AGENT / "scripts" / "compose_downloadthat_ad07_overlays.py")], check=True)


def assemble():
    subprocess.run([sys.executable, str(COMFY_AGENT / "scripts" / "assemble_downloadthat_ad07.py")], check=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "validate":
        sys.exit(0 if validate() else 1)
    elif cmd == "compose":
        compose()
    elif cmd == "assemble":
        assemble()
    elif cmd == "all":
        if not validate():
            sys.exit(1)
        compose()
        assemble()
    else:
        print(__doc__)
        sys.exit(2)
