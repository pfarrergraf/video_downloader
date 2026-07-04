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
