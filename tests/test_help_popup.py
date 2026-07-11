from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "video_downloader" / "web" / "static" / "index.html"


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_help_button_and_overlay_markup_present() -> None:
    html = _html()
    assert 'id="help-open-btn"' in html
    assert 'id="help-overlay"' in html
    assert 'id="help-close-btn"' in html


def test_help_open_and_close_are_wired() -> None:
    html = _html()
    assert "$('help-open-btn').addEventListener('click', () => {" in html
    open_handler = html.split("$('help-open-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-overlay" in open_handler and "remove('hidden')" in open_handler

    close_handler = html.split("$('help-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-overlay" in close_handler and "add('hidden')" in close_handler


def test_help_walkthrough_has_no_mandatory_visible_text() -> None:
    # Every real-language string in the walkthrough must live in a .sr-only
    # span (or an aria-label) - the icons and arrows alone must carry the
    # meaning, per the "an illiterate person must be able to follow this"
    # requirement. A visible <h2>/<p> here would defeat that.
    html = _html()
    help_block = html.split('id="help-overlay"', 1)[1].split("</div>\n\n<div id=\"app\"", 1)[0]
    assert "<h2" not in help_block
    assert "<p " not in help_block and "<p>" not in help_block
    # Each step's translated copy must be visually hidden.
    for step_key in ("app.help.step1", "app.help.step2", "app.help.step3"):
        assert f'class="sr-only" data-i18n="{step_key}"' in help_block


def test_help_steps_use_icons_and_arrows_only() -> None:
    html = _html()
    help_block = html.split('id="help-overlay"', 1)[1].split("</div>\n\n<div id=\"app\"", 1)[0]
    steps = re.findall(r'<div class="help-step">(.*?)</div>', help_block, re.DOTALL)
    assert len(steps) == 3
    for step in steps:
        assert step.count('class="help-icon"') >= 2
        assert 'aria-hidden="true"' in step


def test_i18n_help_keys_present_in_both_locale_trees() -> None:
    for tree in [
        ROOT / "video_downloader" / "web" / "static" / "i18n",
        ROOT / "pro" / "website" / "i18n",
    ]:
        for path in sorted(tree.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            help_strings = data.get("app", {}).get("help", {})
            for key in ("button_label", "close_label", "step1", "step2", "step3"):
                assert help_strings.get(key), f"missing app.help.{key} in {path}"
