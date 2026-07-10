from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "pro" / "website" / "functions",
    ROOT / "pro" / "website" / "migrations",
    ROOT / "pro" / "website" / "partner.html",
    ROOT / "pro" / "website" / "partner-dashboard.html",
    ROOT / "pro" / "website" / "partner-admin.html",
    ROOT / "pro" / "website" / "partnerbedingungen.html",
    ROOT / "pro" / "website" / "partner-datenschutz.html",
    ROOT / "docs" / "AFFILIATE_PROGRAM_IMPLEMENTATION.md",
    ROOT / "android" / "app" / "src" / "main",
]

SECRET_PATTERNS = {
    "Stripe secret key": re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    "Stripe webhook secret": re.compile(r"\bwhsec_[A-Za-z0-9]{16,}\b"),
    "Resend API key": re.compile(r"\bre_[A-Za-z0-9]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _files() -> list[Path]:
    result: list[Path] = []
    for target in TARGETS:
        if target.is_file():
            result.append(target)
        elif target.is_dir():
            result.extend(
                path
                for path in target.rglob("*")
                if path.is_file() and path.suffix.lower() in {".js", ".html", ".sql", ".md", ".kt", ".xml"}
            )
    return result


def test_affiliate_changes_contain_no_embedded_secrets() -> None:
    findings: list[str] = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert not findings, "Embedded credentials found:\n" + "\n".join(findings)
