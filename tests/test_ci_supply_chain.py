"""Regression guard for immutable third-party GitHub Actions references."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PINNED_RE = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def test_third_party_actions_are_pinned_to_commit_sha() -> None:
    violations: list[str] = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for reference in USES_RE.findall(workflow.read_text(encoding="utf-8")):
            if reference.startswith("./"):
                continue
            if not PINNED_RE.fullmatch(reference):
                violations.append(f"{workflow.relative_to(ROOT)}: {reference}")
    assert not violations, "Unpinned GitHub Actions:\n" + "\n".join(violations)
