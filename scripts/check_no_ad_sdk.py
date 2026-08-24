"""Fail closed if a known advertising SDK enters shipped product sources."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    ROOT / "android" / "app" / "src",
    ROOT / "video_downloader",
    ROOT / "pro" / "website" / "functions",
)
MANIFESTS = (
    ROOT / "android" / "app" / "build.gradle",
    ROOT / "android" / "build.gradle",
    ROOT / "android" / "settings.gradle",
    ROOT / "pyproject.toml",
    ROOT / "uv.lock",
)
TEXT_SUFFIXES = {".gradle", ".java", ".js", ".json", ".kt", ".kts", ".py", ".toml", ".xml"}
AD_SDK_PATTERNS = {
    "Google Mobile Ads": re.compile(r"play-services-ads|com\.google\.android\.gms\.ads|\bMobileAds\b", re.I),
    "Google Ad Manager": re.compile(r"com\.google\.android\.gms\.ads\.admanager|doubleclick", re.I),
    "Meta Audience Network": re.compile(r"audience-network-sdk|com\.facebook\.ads", re.I),
    "AppLovin": re.compile(r"applovin", re.I),
    "ironSource": re.compile(r"ironsource|levelplay", re.I),
    "Unity Ads": re.compile(r"unity[-_. ]?ads|com\.unity3d\.ads", re.I),
    "Vungle": re.compile(r"vungle", re.I),
    "Chartboost": re.compile(r"chartboost", re.I),
    "Start.io": re.compile(r"startapp|start\.io", re.I),
    "MoPub": re.compile(r"mopub", re.I),
}


def shipped_text_files(root: Path = ROOT) -> list[Path]:
    files = [path for path in MANIFESTS if path.exists()]
    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue
        files.extend(
            path for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
        )
    files.extend(root.glob("package*.json"))
    return sorted(set(files))


def find_ad_sdk_references(files: list[Path] | None = None) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in files or shipped_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for sdk, pattern in AD_SDK_PATTERNS.items():
            for match in pattern.finditer(text):
                try:
                    display_path = str(path.relative_to(ROOT))
                except ValueError:
                    display_path = str(path)
                findings.append({
                    "sdk": sdk,
                    "path": display_path,
                    "line": text.count("\n", 0, match.start()) + 1,
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    files = shipped_text_files()
    findings = find_ad_sdk_references(files)
    result = {"filesScanned": len(files), "advertisingSdkReferences": findings}
    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif findings:
        for finding in findings:
            print(f"{finding['path']}:{finding['line']}: {finding['sdk']}")
    else:
        print(f"No advertising SDK references found in {len(files)} shipped source/dependency files.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
