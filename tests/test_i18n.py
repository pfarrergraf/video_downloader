from __future__ import annotations

import json
from pathlib import Path

APP_I18N_DIR = Path(__file__).resolve().parent.parent / "video_downloader" / "web" / "static" / "i18n"
WEBSITE_I18N_DIR = Path(__file__).resolve().parent.parent / "pro" / "website" / "i18n"


def _flatten(d: dict, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, full_key))
        else:
            out[full_key] = value
    return out


def _english_keys(i18n_dir: Path) -> set[str]:
    source = json.loads((i18n_dir / "en.json").read_text(encoding="utf-8"))
    return set(_flatten(source).keys())


def _language_files(i18n_dir: Path) -> list[Path]:
    return sorted(p for p in i18n_dir.glob("*.json") if p.name != "en.json")


def test_english_source_files_exist_and_match() -> None:
    # The app and website ship their own copy of the same strings so each can
    # be deployed independently; they must never drift apart silently.
    assert (APP_I18N_DIR / "en.json").is_file()
    assert (WEBSITE_I18N_DIR / "en.json").is_file()
    assert _english_keys(APP_I18N_DIR) == _english_keys(WEBSITE_I18N_DIR)


def test_every_translation_file_has_the_same_keys_as_english() -> None:
    for i18n_dir in (APP_I18N_DIR, WEBSITE_I18N_DIR):
        expected = _english_keys(i18n_dir)
        for path in _language_files(i18n_dir):
            data = json.loads(path.read_text(encoding="utf-8"))
            actual = set(_flatten(data).keys())
            assert actual == expected, f"{path} has mismatched keys: missing={expected - actual}, extra={actual - expected}"


def test_every_translation_value_is_a_non_empty_string() -> None:
    for i18n_dir in (APP_I18N_DIR, WEBSITE_I18N_DIR):
        for path in list(_language_files(i18n_dir)) + [i18n_dir / "en.json"]:
            flat = _flatten(json.loads(path.read_text(encoding="utf-8")))
            for key, value in flat.items():
                assert isinstance(value, str) and value.strip(), f"{path}:{key} is empty"


def test_placeholders_are_preserved_across_languages() -> None:
    import re

    placeholder_re = re.compile(r"\{[a-z_]+\}")
    for i18n_dir in (APP_I18N_DIR, WEBSITE_I18N_DIR):
        english_flat = _flatten(json.loads((i18n_dir / "en.json").read_text(encoding="utf-8")))
        english_placeholders = {k: set(placeholder_re.findall(v)) for k, v in english_flat.items()}
        for path in _language_files(i18n_dir):
            flat = _flatten(json.loads(path.read_text(encoding="utf-8")))
            for key, expected_placeholders in english_placeholders.items():
                if not expected_placeholders:
                    continue
                actual_placeholders = set(placeholder_re.findall(flat.get(key, "")))
                assert actual_placeholders == expected_placeholders, (
                    f"{path}:{key} lost or changed placeholders: "
                    f"expected {expected_placeholders}, got {actual_placeholders}"
                )


INDEX_HTML = Path(__file__).resolve().parent.parent / "video_downloader" / "web" / "static" / "index.html"


def test_limit_copy_never_hardcodes_numbers() -> None:
    # The free-tier count drifted between 1, 3 and 5 across surfaces before
    # it was moved behind {limit}/{hours} placeholders filled from
    # /api/settings. A digit creeping back into these strings means the
    # drift is back - keep them placeholder-only in every language.
    import re

    digit_re = re.compile(r"\d")
    for i18n_dir in (APP_I18N_DIR, WEBSITE_I18N_DIR):
        for path in list(_language_files(i18n_dir)) + [i18n_dir / "en.json"]:
            flat = _flatten(json.loads(path.read_text(encoding="utf-8")))
            for key in ("app.limit.body", "app.license.status_free"):
                value = str(flat.get(key, ""))
                assert value, f"{path}:{key} is missing"
                assert "{limit}" in value, f"{path}:{key} lost the {{limit}} placeholder"
                assert not digit_re.search(value), f"{path}:{key} hardcodes a number again: {value!r}"


def test_new_ux_keys_exist_in_source() -> None:
    keys = _english_keys(APP_I18N_DIR)
    for expected in (
        "app.home.url_label",
        "app.home.download_btn",
        "app.home.video_toggle",
        "app.home.audio_toggle",
        "app.home.advanced_summary",
        "app.home.quality_label",
        "app.status.pending",
        "app.status.in_progress",
        "app.status.completed",
        "app.status.failed",
        "app.status.cancelled",
        "app.errors.unknown",
        "app.errors.engine_outdated",
        "app.errors.video_unavailable",
        "app.clipboard.insert_btn",
        "app.theme.label",
        "app.queue.details_toggle",
        # Page scraping (find images/PDFs/other files on a page) was
        # reintroduced under the "Advanced" section per owner request,
        # after being fully removed in the one-screen redesign - this time
        # it stays a collapsed sub-section rather than its own top-level
        # card, so it doesn't regress the simplified main flow.
        "app.home.file_toggle",
        "app.scrape.label",
        "app.scrape.scan_btn",
        "app.scrape.download_btn",
    ):
        assert expected in keys


def test_index_html_has_no_external_resource_dependencies() -> None:
    # The app must render fully offline-from-the-APK: no Google Fonts, no
    # CDN scripts/styles. (Outbound <a href> links to the project website
    # are fine - they're navigation, not render dependencies.)
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "preconnect" not in html
    import re

    for tag, attr in (("link", "href"), ("script", "src"), ("img", "src")):
        for match in re.finditer(rf"<{tag}[^>]*\s{attr}=\"([^\"]+)\"", html):
            url = match.group(1)
            assert not url.startswith(("http://", "https://", "//")), (
                f"index.html loads an external resource: <{tag} {attr}={url!r}>"
            )
