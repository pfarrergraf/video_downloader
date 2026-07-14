from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (ROOT / "pro" / "website" / "functions", ROOT / "android" / "app" / "src")
PATTERNS = {
    "provider secret": re.compile(r"\b(?:sk_(?:live|test)|whsec_|re_)[A-Za-z0-9_-]{16,}\b"),
    "private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\s]{64,}"
    ),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
}


def test_active_app_and_backend_contain_no_embedded_secrets() -> None:
    findings = []
    for root in TARGETS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".js", ".kt", ".xml", ".sql"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert not findings, "Embedded credentials found:\n" + "\n".join(findings)
