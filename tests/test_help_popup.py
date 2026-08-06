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
    open_helper = html.split("function openHelp() {", 1)[1].split("}\n", 1)[0]
    assert "initHelpAnimation()" in open_helper
    assert "$('help-open-btn').addEventListener('click', openHelp);" in html


def test_help_open_and_close_are_wired() -> None:
    html = _html()
    assert "$('help-open-btn').addEventListener('click', openHelp);" in html
    open_helper = html.split("function openHelp() {", 1)[1].split("}\n", 1)[0]
    assert "help-overlay" in open_helper and "remove('hidden')" in open_helper

    close_handler = html.split("$('help-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "help-overlay" in close_handler and "add('hidden')" in close_handler


def test_reopening_help_animation_always_restarts_from_scene_one() -> None:
    # Bug report: closing the tutorial and reopening it must start over at
    # scene 1 - it must not resume wherever a previous run (or a stray tap,
    # see test_help_animation_taps_cannot_freeze_the_loop below) left off.
    # initHelpAnimation() only wires things up once (guarded by
    # helpAnimationStarted), so the actual restart has to be a separate
    # function openHelp() calls every time, not just on the first open.
    html = _html()
    assert "let stopHelpAnimation = () => {};" in html
    assert "let restartHelpAnimation = () => {};" in html
    init_body = html.split("function initHelpAnimation() {", 1)[1].split("\n}\n", 1)[0]
    assert "stopHelpAnimation = () => {" in init_body
    assert "restartHelpAnimation = () => {" in init_body

    open_helper = html.split("function openHelp() {", 1)[1].split("}\n", 1)[0]
    assert "initHelpAnimation()" in open_helper
    assert "restartHelpAnimation()" in open_helper

    close_handler = html.split("$('help-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "stopHelpAnimation()" in close_handler
    guide_open = html.split("$('help-guide-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "stopHelpAnimation()" in guide_open


def test_closing_the_tutorial_silences_already_scheduled_audio() -> None:
    # Bug report: the tutorial kept playing its sound after being closed.
    # Its sounds are not driven by setTimeout - playDownloadWhirr() books a
    # 2s hum plus ~18 tick oscillators onto the WebAudio timeline in one go,
    # with absolute start/stop times, so clearTimers() (which only cancels
    # pending JS timers) cannot stop them. Everything therefore has to route
    # through one swappable gain node that closing can cut, rather than
    # connecting to audioCtx.destination directly.
    html = _html()
    assert "let audioBus = null;" in html
    assert "function silenceAudio() {" in html
    assert "function resumeAudio() {" in html

    # No sound may bypass the bus by connecting straight to the destination.
    # Only the bus itself legitimately reaches audioCtx.destination.
    init_body = html.split("function initHelpAnimation() {", 1)[1].split("\n}\n", 1)[0]
    assert "audioBus.connect(audioCtx.destination)" in init_body
    assert init_body.replace("audioBus.connect(audioCtx.destination)", "").count(
        "connect(audioCtx.destination)"
    ) == 0
    assert init_body.count("connect(audioBus)") >= 4  # click, swipe, whirr hum + ticks

    silence = html.split("function silenceAudio() {", 1)[1].split("\n  }", 1)[0]
    assert "audioBus.disconnect()" in silence
    assert "audioCtx.suspend()" in silence

    # The real assignments live inside initHelpAnimation(); the module-level
    # "let stopHelpAnimation = () => {};" placeholders are empty by design.
    stop_body = init_body.split("stopHelpAnimation = () => {", 1)[1].split("};", 1)[0]
    assert "clearTimers()" in stop_body and "silenceAudio()" in stop_body
    restart_body = init_body.split("restartHelpAnimation = () => {", 1)[1].split("};", 1)[0]
    assert "resumeAudio()" in restart_body


def test_backgrounding_the_app_also_silences_the_tutorial() -> None:
    # Swiping the app away mid-scene must not leave the whirr playing out.
    html = _html()
    handler = html.split("document.addEventListener('visibilitychange', () => {", 1)[1].split(
        "\n  });", 1
    )[0]
    assert "clearTimers()" in handler and "silenceAudio()" in handler
    assert "resumeAudio()" in handler


def test_help_animation_taps_cannot_freeze_the_loop() -> None:
    # Bug report: tapping inside the phone mockup mid-animation (the
    # Video/Audio buttons in the "format" scene, the share CTA, ...) used to
    # call clearTimers() and jump scenes with nothing ever rescheduling
    # play() afterwards, leaving the loop stuck forever on whatever scene it
    # jumped to. Those buttons are only meant to be real controls on the
    # marketing site's interactive hero, not in this passive in-app replay -
    # pointer-events: none makes them inert here instead of wiring up a
    # click handler that can kill the loop.
    html = _html()
    assert "#help-overlay [data-pc3-next] { pointer-events: none; }" in html
    assert "e.target.closest('[data-pc3-next]')" not in html


def test_help_close_and_guide_icons_are_flex_centered() -> None:
    # Both the "✕" and the "📖" glyphs sat off-center in their circles - the
    # global `button` rule's default padding only self-cancels under flex
    # centering (same as .icon-btn, which was already fine for this reason).
    close_rule = _html().split("#help-close-btn {", 1)[1].split("}", 1)[0]
    assert "display: flex" in close_rule and "align-items: center" in close_rule and "justify-content: center" in close_rule
    guide_rule = _html().split(".help-guide-btn {", 1)[1].split("}", 1)[0]
    assert "display: flex" in guide_rule and "align-items: center" in guide_rule and "justify-content: center" in guide_rule


def test_help_guide_btn_pulses_continuously_while_animation_is_open() -> None:
    # The book icon is the only hint that a written guide exists behind the
    # animation - it should keep drawing the eye the whole time the
    # animation overlay is open, not just once. A plain infinite CSS
    # animation is enough: #help-overlay's own display:none when hidden
    # already stops (and resets) it, no JS start/stop needed.
    html = _html()
    guide_rule = html[html.index(".help-guide-btn {"):html.index(".help-guide-btn {") + 900]
    assert "animation: icon-btn-glow-pulse 1.8s ease-in-out infinite;" in guide_rule


def test_help_open_btn_glows_once_after_the_auto_shown_tutorial_closes() -> None:
    # Per product feedback: some testers never noticed the manual ? button,
    # so the tutorial now auto-opens once on first run (see the test above).
    # When that auto-shown tutorial is dismissed, the header (and its ?
    # button) becomes visible again for the first time - glow it briefly so
    # people know how to reopen it, without nagging on every manual open/close.
    html = _html()
    assert "let firstRunAutoOpened = false;" in html
    auto_show = html.split("function maybeShowFirstRunHelp() {", 1)[1].split(
        "function glowHelpButtonOnce", 1
    )[0]
    assert "firstRunAutoOpened = true;" in auto_show
    glow_fn = html.split("function glowHelpButtonOnce() {", 1)[1].split("}\n", 1)[0]
    assert "if (!firstRunAutoOpened) return;" in glow_fn
    assert "firstRunAutoOpened = false;" in glow_fn
    assert "classList.add('glow-pulse')" in glow_fn

    close_handler = html.split("$('help-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "glowHelpButtonOnce()" in close_handler
    guide_close = html.split("$('help-guide-close-btn').addEventListener('click', () => {", 1)[1].split("});", 1)[0]
    assert "glowHelpButtonOnce()" in guide_close
    assert "@keyframes icon-btn-glow-pulse" in html
    assert ".icon-btn.glow-pulse { animation: icon-btn-glow-pulse 1.1s ease-in-out 3; }" in html


def test_native_first_run_help_is_one_time_and_does_not_cover_shared_link_picker() -> None:
    html = _html()
    assert "const FIRST_RUN_HELP_KEY = 'downloadthat:first-run-help:v1';" in html
    helper = html.split("function maybeShowFirstRunHelp() {", 1)[1].split(
        "$('help-open-btn').addEventListener", 1
    )[0]
    assert "window.AndroidBridge" in helper
    assert "share-format-overlay" in helper
    assert "localStorage.getItem(FIRST_RUN_HELP_KEY)" in helper
    assert "requestAnimationFrame(openHelp)" in helper
    assert "localStorage.setItem(FIRST_RUN_HELP_KEY, '1')" in html
    authenticated = html.split("async function setAuthed(authed) {", 1)[1].split(
        "$('terms-checkbox').addEventListener", 1
    )[0]
    assert authenticated.index("deliverPendingSharedUrl();") < authenticated.index("maybeShowFirstRunHelp();")


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
    assert 'href="mailto:gpt.assist.benjamin@gmail.com"' in guide_block


def test_settings_expose_support_and_google_play_rating_actions() -> None:
    html = _html()
    settings = html.split('id="settings-overlay"', 1)[1].split('id="limit-overlay"', 1)[0]
    assert 'href="mailto:gpt.assist.benjamin@gmail.com"' in settings
    assert 'id="rate-app-btn"' in settings
    assert 'href="https://play.google.com/store/apps/details?id=de.classydl.app"' in settings
    assert "window.AndroidBridge.openPlayStore();" in html


def test_native_purchase_errors_are_localized_instead_of_showing_raw_codes() -> None:
    html = _html()
    callback = html.split("window.onNativeEntitlementResult = function(result) {", 1)[1].split(
        "function handleNativePurchase", 1
    )[0]
    for code in (
        "purchase_pending",
        "product_unavailable",
        "billing_unavailable",
        "no_purchase_found",
    ):
        assert code in callback
    assert "toast(result.error)" not in callback
    assert "app.license.purchase_failed_toast" in callback


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


def test_i18n_purchase_feedback_and_rating_keys_present_in_both_locale_trees() -> None:
    for tree in [
        ROOT / "video_downloader" / "web" / "static" / "i18n",
        ROOT / "pro" / "website" / "i18n",
    ]:
        for path in sorted(tree.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            license_strings = data.get("app", {}).get("license", {})
            for key in (
                "purchase_pending_toast",
                "product_unavailable_toast",
                "billing_unavailable_toast",
                "no_purchase_found_toast",
                "purchase_failed_toast",
            ):
                assert license_strings.get(key), f"missing app.license.{key} in {path}"
            assert data.get("app", {}).get("about", {}).get("rate_btn"), (
                f"missing app.about.rate_btn in {path}"
            )
