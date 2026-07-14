"""Keep active production endpoints on the dedicated DownloadThat zone."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_FILES = (
    ROOT / "README.md",
    ROOT / "classydl_web_entry.py",
    ROOT / "android" / "app" / "build.gradle",
    ROOT / ".github" / "workflows" / "android-release.yml",
    ROOT / ".github" / "workflows" / "deploy-pro-website.yml",
    ROOT / ".github" / "workflows" / "google-play-reconciliation.yml",
    ROOT / "video_downloader" / "web" / "static" / "index.html",
)


def test_active_production_urls_use_dedicated_domain() -> None:
    stale = ("downloadthat.pages.dev", "downloadthat.gaistreich.com", "downloadthat.geistreich.com")
    violations = []
    for path in ACTIVE_FILES:
        text = path.read_text(encoding="utf-8")
        for hostname in stale:
            if hostname in text:
                violations.append(f"{path.relative_to(ROOT)}: {hostname}")
    assert not violations, "Stale production domains:\n" + "\n".join(violations)


def test_canonical_domain_is_present_in_every_runtime_surface() -> None:
    for path in ACTIVE_FILES:
        assert "downloadthat.app" in path.read_text(encoding="utf-8"), path.relative_to(ROOT)
