"""Fail closed when retired or misleading public claims re-enter active sources."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".srt", ".svg", ".txt"}

ACTIVE_ROOTS = (
    ROOT / "pro" / "website",
    ROOT / "video_downloader" / "web" / "static",
    ROOT / "store_assets",
)

ACTIVE_FILES = (
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    ROOT / "docs" / "MARKETING_LEGAL_GUARDRAILS.md",
    ROOT / "docs" / "WORKPLAN.md",
    ROOT / "docs" / "PLAY_STORE_READINESS.md",
    ROOT / "docs" / "PLAY_CONSOLE_INTERNAL_TESTING_PREP.md",
)

EXCLUDED_PARTS = {
    ".git",
    "node_modules",
    "tests",
}

FORBIDDEN = {
    "universal website support": re.compile(
        r"(?:\bfrom\s+(?:almost\s+|nearly\s+|virtually\s+|most\s+|any\s+|every\s+)"
        r"(?:site|website)s?\b|\b(?:almost|nearly|virtually)\s+any\s+(?:site|website|video)\b|"
        r"\bworks?\s+(?:on|with)\s+(?:almost\s+|most\s+|any\s+|every\s+)(?:site|website)s?\b)",
        re.IGNORECASE,
    ),
    "universal German support": re.compile(
        r"\b(?:von|auf|aus)\s+(?:fast\s+)?(?:jeder|jedem|jeder\s+beliebigen)\s+"
        r"(?:seite|website|video)\b|\bvon\s+den\s+meisten\s+(?:seiten|websites)\b",
        re.IGNORECASE,
    ),
    "anti-store positioning": re.compile(
        r"\b(?:no|without)\s+play\s*store(?:\s+needed)?\b|"
        r"\b(?:kein|ohne)\s+play\s*store(?:\s+nötig)?\b|"
        r"\bnot\s+in\s+(?:an|the)\s+app\s*store\b",
        re.IGNORECASE,
    ),
    "absolute local-only privacy claim": re.compile(
        r"\b100\s*%\s+(?:local|lokal|on[- ]device|auf\s+(?:dem|deinem)\s+gerät)\b|"
        r"\b(?:everything|the\s+whole\s+app)\s+runs\s+locally\b|"
        r"\balles\s+läuft\s+lokal\b|\bruns\s+entirely\s+on\s+your\s+device\b|"
        r"\b(?:nothing\s+gets|nichts\s+wird).*\b(?:uploaded|hochgeladen)\b",
        re.IGNORECASE,
    ),
}


def _active_text_files() -> list[Path]:
    files = [path for path in ACTIVE_FILES if path.exists()]
    for root in ACTIVE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative_parts = set(path.relative_to(ROOT).parts)
            if relative_parts & EXCLUDED_PARTS:
                continue
            files.append(path)
    return sorted(set(files))


def find_violations() -> list[str]:
    failures: list[str] = []
    retired_assets = ROOT / "pro" / "website" / "assets" / "influencer"
    if retired_assets.exists():
        failures.append(
            "retired public affiliate assets exist: pro/website/assets/influencer"
        )

    for path in _active_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in FORBIDDEN.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                excerpt = " ".join(match.group(0).split())
                failures.append(f"{path.relative_to(ROOT)}:{line}: {label}: {excerpt!r}")
    return failures


def main() -> int:
    failures = find_violations()
    if failures:
        print("Public-claims policy violations:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Public-claims policy: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
