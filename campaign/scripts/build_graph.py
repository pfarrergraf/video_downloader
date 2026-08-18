"""Run a named DownloadThat! campaign workflow already checked into
gAIstreich-comfy-agent's workflows/api/, and sync the finished output back
into campaign/raw/.

Corrected from an earlier draft that assumed comfy-agent held generic,
parametrizable templates — it doesn't. Every project there (Luther,
"alltagsservice", now this one) checks in its own named, project-specific
workflow graph with the prompt baked in (see ../README.md's "Split of
responsibility"). This script does not build graphs; it runs ones that
already exist under `downloadthat_*.json` and retrieves the result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_RAW = REPO_ROOT / "campaign" / "raw"

WSL_COMFY_AGENT = "/home/benjamin_graf/projects/gAIstreich-comfy-agent"
WSL_COMFYUI_OUTPUT = "/home/benjamin_graf/ComfyUI/output"


def wsl_path(windows_path: Path) -> str:
    rel = windows_path.resolve().relative_to(REPO_ROOT)
    drive = REPO_ROOT.drive.rstrip(":").lower()
    root_rel = REPO_ROOT.relative_to(REPO_ROOT.anchor).as_posix()
    return f"/mnt/{drive}/{root_rel}/{rel.as_posix()}"


def run_workflow(name: str, timeout: int = 600) -> dict:
    """Run `workflows/api/<name>.json` via gai-comfy. Returns its result dict
    (includes the output filename(s)/subfolder under ComfyUI's own output/)."""
    result = subprocess.run(
        [
            "wsl.exe", "-e", "bash", "-lc",
            f"cd {WSL_COMFY_AGENT} && uv run gai-comfy run workflows/api/{name}.json --timeout {timeout}",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gai-comfy run failed for '{name}':\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def sync_outputs(result: dict, dest_subdir: str) -> list[Path]:
    """Copy every output file referenced in a gai-comfy run() result from
    ComfyUI's output/ into campaign/raw/<dest_subdir>/."""
    dest_dir = CAMPAIGN_RAW / dest_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for node_output in result.get("outputs", {}).values():
        for kind in ("images", "gifs"):  # ComfyUI reports both images and videos under these keys
            for item in node_output.get(kind, []):
                remote = f"{WSL_COMFYUI_OUTPUT}/{item['subfolder']}/{item['filename']}"
                local = dest_dir / item["filename"]
                subprocess.run(
                    ["wsl.exe", "-e", "bash", "-lc", f"cp '{remote}' '{wsl_path(local)}'"],
                    check=True,
                )
                copied.append(local)
    return copied


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_name", help="e.g. downloadthat_spy_portrait_v1")
    parser.add_argument("dest_subdir", help="subfolder under campaign/raw/ to copy results into")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    result = run_workflow(args.workflow_name, args.timeout)
    files = sync_outputs(result, args.dest_subdir)
    for f in files:
        print(f)
