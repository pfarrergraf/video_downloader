from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_claim_catalog_contains_only_the_six_approved_families() -> None:
    catalog = json.loads((ROOT / "security/PUBLIC_CLAIMS_CATALOG.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in catalog["approved"]] == [
        "no-advertising",
        "free-rolling-quota",
        "pro-app-limit",
        "one-time-local-play-price",
        "up-to-4k",
        "supported-lawful-links",
    ]
    assert {item["id"] for item in catalog["forbidden"]} == {
        "skip-the-ad",
        "universal-source",
        "unqualified-unlimited",
        "absolute-free",
        "fixed-price",
        "absolute-local-offline",
    }


def test_active_locale_claim_slots_use_the_qualified_app_limit_claim() -> None:
    english = json.loads(
        (ROOT / "video_downloader/web/static/i18n/en.json").read_text(encoding="utf-8")
    )
    english_values = (
        english["app"]["license"]["status_free"],
        english["app"]["limit"]["body"],
        english["website"]["pricing"]["lead"],
        english["website"]["pricing"]["feature_unlimited"],
        english["website"]["faq"]["q1_body"],
    )
    for directory in (
        ROOT / "video_downloader/web/static/i18n",
        ROOT / "pro/website/i18n",
    ):
        for path in directory.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            values = (
                data["app"]["license"]["status_free"],
                data["app"]["limit"]["body"],
                data["website"]["pricing"]["lead"],
                data["website"]["pricing"]["feature_unlimited"],
                data["website"]["faq"]["q1_body"],
            )
            assert all("unlimited download" not in value.lower() for value in values)
            assert "{limit}" in values[0]
            assert "{limit}" in values[1] and "{hours}" in values[1]
            if path.stem != "en":
                assert all(value != english_value for value, english_value in zip(values, english_values))
