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


def test_named_platform_demo_rasters_are_not_publicly_deployable() -> None:
    public_assets = ROOT / "pro/website/assets/home"
    assert not (public_assets / "demo-progress.png").exists()
    assert not (public_assets / "demo-done.png").exists()


def test_rejected_legacy_screenshot_upload_modes_are_retired() -> None:
    uploader = (ROOT / "scripts/upload_google_play.mjs").read_text(encoding="utf-8")
    main = uploader.split("async function main()", 1)[1]
    assert "Legacy screenshot upload modes are retired" in main
    assert "screenshot_main.png" not in main
    assert "screenshot_queue.png" not in main
    assert "screenshot_settings.png" not in main


def test_download_queue_never_exposes_source_url_or_hostname() -> None:
    html = (ROOT / "video_downloader/web/static/index.html").read_text(encoding="utf-8")
    assert "name.title = job.source" not in html
    assert "new URL(job.source).hostname" not in html
    assert "if (job.files && job.files.length) return job.files[0].filename;\n  return '';" in html


def test_public_share_instructions_avoid_named_platforms() -> None:
    forbidden = ("youtube", "instagram", "tiktok", "facebook", "vimeo")
    locale_roots = (
        ROOT / "video_downloader/web/static/i18n",
        ROOT / "pro/website/i18n",
    )
    for locale_root in locale_roots:
        for locale_file in locale_root.glob("*.json"):
            app = json.loads(locale_file.read_text(encoding="utf-8"))["app"]
            public_copy = " ".join(
                (app["home"]["share_hint"], app["help"]["anim_step1"])
            ).lower()
            assert not any(name in public_copy for name in forbidden), locale_file


def test_play_flavor_disables_youtube_discovery_and_queueing() -> None:
    gradle = (ROOT / "android/app/build.gradle").read_text(encoding="utf-8")
    main = (ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt").read_text(
        encoding="utf-8"
    )
    search = (ROOT / "android/app/src/main/java/de/classydl/app/SearchActivity.kt").read_text(
        encoding="utf-8"
    )
    runtime = (ROOT / "android/app/src/main/java/de/classydl/app/ServerRuntime.kt").read_text(
        encoding="utf-8"
    )
    android_entry = (ROOT / "video_downloader/android_entry.py").read_text(encoding="utf-8")

    play_flavor = gradle.split("play {", 1)[1].split("direct {", 1)[0]
    assert 'buildConfigField "boolean", "PLAY_POLICY_RESTRICTED", "true"' in play_flavor
    assert "if (BuildConfig.PLAY_POLICY_RESTRICTED) View.GONE" in main
    assert "if (BuildConfig.PLAY_POLICY_RESTRICTED)" in search
    assert "BuildConfig.PLAY_POLICY_RESTRICTED" in runtime
    assert 'frozenset({"youtube.com", "youtu.be"})' in android_entry


def test_android_marketing_does_not_claim_image_downloads() -> None:
    text_sources = [
        ROOT / "docs/GOOGLE_PLAY_ENGLISH_LISTING.md",
        ROOT / "docs/GOOGLE_PLAY_ENGLISH_TEXT.txt",
        ROOT / "docs/GOOGLE_PLAY_MORE_LANGUAGES.txt",
        ROOT / "security/PUBLIC_CLAIMS_POLICY.md",
        ROOT / "store_assets/README.md",
        ROOT / "pro/website/index.html",
        *sorted((ROOT / "store_assets").glob("feature_graphic*.svg")),
        *sorted((ROOT / "pro/website/i18n").glob("*.json")),
    ]
    forbidden = (
        "images",
        "bilder",
        "afbeeldingen",
        "immagini",
        "imágenes",
        "obrazy",
        "图片",
        "画像",
        "изображения",
        "الصور",
    )
    for source in text_sources:
        text = source.read_text(encoding="utf-8").lower()
        assert not any(claim in text for claim in forbidden), source
