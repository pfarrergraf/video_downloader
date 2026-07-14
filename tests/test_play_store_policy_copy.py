import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_taglines_do_not_make_broad_site_support_claims() -> None:
    forbidden = (
        "from any site",
        "from most sites",
        "von den meisten seiten",
        "von fast jeder seite",
    )
    for locale_file in (ROOT / "video_downloader/web/static/i18n").glob("*.json"):
        tagline = json.loads(locale_file.read_text(encoding="utf-8"))["app"]["tagline"].lower()
        assert not any(claim in tagline for claim in forbidden), locale_file.name


def test_store_listing_assets_avoid_named_download_platforms() -> None:
    text_sources = [
        ROOT / "store_assets/README.md",
        ROOT / "store_assets/feature_graphic.svg",
    ]
    forbidden = ("youtube.com", "youtu.be", "instagram.com", "from any site", "almost any site")
    for source in text_sources:
        text = source.read_text(encoding="utf-8").lower()
        assert not any(claim in text for claim in forbidden), source.name
