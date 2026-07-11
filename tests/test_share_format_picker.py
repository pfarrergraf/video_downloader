from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "video_downloader" / "web" / "static" / "index.html"


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_share_format_overlay_markup_present() -> None:
    html = _html()
    assert 'id="share-format-overlay"' in html
    assert 'data-i18n="app.share_format.title"' in html
    assert 'id="share-format-video-btn"' in html
    assert 'id="share-format-audio-btn"' in html
    assert 'id="share-format-cancel-btn"' in html


def test_share_intent_shows_picker_instead_of_auto_downloading() -> None:
    html = _html()
    # The old behaviour called startDownload() directly inside onSharedUrl;
    # it must now only reveal the picker and let the button handlers decide.
    on_shared_url = html.split("window.onSharedUrl = (url) => {", 1)[1].split("};", 1)[0]
    assert "startDownload()" not in on_shared_url
    assert "share-format-overlay" in on_shared_url


def test_picker_buttons_set_kind_then_download_then_close() -> None:
    html = _html()
    for btn_id, kind in [("share-format-video-btn", "video"), ("share-format-audio-btn", "audio")]:
        handler = html.split(f"$('{btn_id}').addEventListener('click', () => {{", 1)[1].split("});", 1)[0]
        assert f"setMediaKind('{kind}')" in handler
        assert "closeShareFormatPicker()" in handler
        assert "startDownload()" in handler


def test_cancel_button_only_closes_the_picker() -> None:
    html = _html()
    assert "$('share-format-cancel-btn').addEventListener('click', closeShareFormatPicker);" in html


def test_i18n_key_present_in_both_locale_trees() -> None:
    import json

    for tree in [
        ROOT / "video_downloader" / "web" / "static" / "i18n",
        ROOT / "pro" / "website" / "i18n",
    ]:
        for path in sorted(tree.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            title = data.get("app", {}).get("share_format", {}).get("title")
            assert title, f"missing app.share_format.title in {path}"
