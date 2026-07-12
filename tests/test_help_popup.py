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
    assert 'id="help-guide-btn"' in html
    assert 'id="help-guide-overlay"' in html
    assert 'id="help-guide-close-btn"' in html


def test_help_overlay_embeds_the_hero_cinema_animation() -> None:
    # Per product feedback, the old icon-only 3-step walkthrough was
    # replaced with the exact same "Product Cinema" animation used on the
    # marketing homepage (pro/website/index.html's .pc3 hero) - same six
    # scenes, same classes/data attributes.
    html = _html()
    help_block = html.split('id="help-overlay"', 1)[1].split('id="help-guide-overlay"', 1)[0]
    assert "data-pc3-root" in help_block
    for state in ("source", "share", "format", "stream", "inside", "success"):
        assert f'data-pc3-view="{state}"' in help_block


def test_help_animation_is_lazily_initialized() -> None:
    # The animation's canvas particle system + infinite auto-loop timers
    # must not run in the background for the entire time the app is open -
    # only once someone actually opens the help overlay. The only call site
    # should be inside the help-open-btn click handler - not a bare
    # top-level invocation like the website's own auto-running copy.
    html = _html()
    assert "function initHelpAnimation()" in html
    assert "let helpAnimationStarted = false;" in html
    assert html.count("initHelpAnimation();") == 1  # exactly one call site
    open_handler = html.split("$('help-open-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "initHelpAnimation()" in open_handler


def test_help_open_and_close_are_wired() -> None:
    html = _html()
    assert "$('help-open-btn').addEventListener('click', () => {" in html
    open_handler = html.split("$('help-open-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-overlay" in open_handler and "remove('hidden')" in open_handler

    close_handler = html.split("$('help-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-overlay" in close_handler and "add('hidden')" in close_handler


def test_help_guide_button_switches_to_written_steps() -> None:
    html = _html()
    guide_open = html.split("$('help-guide-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-overlay" in guide_open and "add('hidden')" in guide_open
    assert "help-guide-overlay" in guide_open and "remove('hidden')" in guide_open

    guide_close = html.split("$('help-guide-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-guide-overlay" in guide_close and "add('hidden')" in guide_close


def test_help_guide_has_six_visible_written_steps() -> None:
    # Unlike the animation (icons + motion only), the guide is meant to be
    # read - its six steps are real, visible, translated text, not sr-only.
    html = _html()
    guide_block = html.split('id="help-guide-overlay"', 1)[1].split("<div id=\"app\"", 1)[0]
    assert 'data-i18n="app.help.guide_title"' in guide_block
    steps = re.findall(r'data-i18n="app\.help\.guide_step(\d)"', guide_block)
    assert steps == [str(n) for n in range(1, 7)]
    assert "sr-only" not in guide_block


def test_i18n_help_keys_present_in_both_locale_trees() -> None:
    for tree in [
        ROOT / "video_downloader" / "web" / "static" / "i18n",
        ROOT / "pro" / "website" / "i18n",
    ]:
        for path in sorted(tree.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            help_strings = data.get("app", {}).get("help", {})
            for key in (
                "button_label", "close_label",
                "guide_btn", "guide_title",
                "guide_step1", "guide_step2", "guide_step3",
                "guide_step4", "guide_step5", "guide_step6",
            ):
                assert help_strings.get(key), f"missing app.help.{key} in {path}"
