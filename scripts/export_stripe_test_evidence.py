"""Export Stripe test-mode objects before permanent commerce decommissioning."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


ENDPOINTS = ("checkout/sessions", "charges", "refunds", "customers")


def fetch_all(endpoint: str, key: str) -> list[dict]:
    rows: list[dict] = []
    starting_after = ""
    while True:
        query = {"limit": "100"}
        if starting_after:
            query["starting_after"] = starting_after
        request = urllib.request.Request(
            f"https://api.stripe.com/v1/{endpoint}?{urllib.parse.urlencode(query)}",
            headers={"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()},
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS host
            payload = json.load(response)
        page = payload.get("data", [])
        rows.extend(page)
        if not payload.get("has_more") or not page:
            return rows
        starting_after = page[-1]["id"]


def main() -> int:
    key = os.environ.get("STRIPE_TEST_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        raise SystemExit("Refusing export: STRIPE_TEST_SECRET_KEY must be a Stripe test-mode key")
    output = Path(os.environ.get("STRIPE_EXPORT_DIR", "stripe-test-export"))
    output.mkdir(parents=True, exist_ok=True)
    for endpoint in ENDPOINTS:
        path = output / f"{endpoint.replace('/', '-')}.json"
        path.write_text(json.dumps(fetch_all(endpoint, key), indent=2) + "\n", encoding="utf-8")
    files = sorted(output.glob("*.json"))
    (output / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files),
        encoding="ascii",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
