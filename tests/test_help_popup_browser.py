"""End-to-end browser tests for the in-app tutorial overlay.

The rest of the help-popup coverage (tests/test_help_popup.py) asserts on the
*source text* of index.html, which is enough to pin a wiring decision but
cannot tell whether the tutorial actually behaves correctly once a browser
lays it out and runs its timers. These three bugs were all reported from a
real device and none of them are visible to a string assertion:

  * the written guide rendered as a plain block in document flow instead of a
    modal, so the app stayed visible behind it and the close button was pushed
    off-screen;
  * the animation restarted from scene 1 forever, because visibilitychange
    (which an Android WebView fires far more often than "user left and came
    back") called play() unconditionally;
  * the tutorial re-opened itself, because setAuthed(true) can run more than
    once per launch.

So these drive a real Chromium against a real ClassyDLServer. Skipped when
Playwright or its browser binary is unavailable - install with
`python -m playwright install chromium`.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from video_downloader.queue_store import QueueStore
from video_downloader.web.server import create_server

sync_api = pytest.importorskip("playwright.sync_api")

PASSWORD = "crypt-keeper"
PC3_ROOT = "#help-overlay [data-pc3-root]"
PHASE = f"document.querySelector({PC3_ROOT!r}).dataset.pc3Phase"


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            launched = p.chromium.launch()
        except Exception as exc:  # binary not downloaded in this environment
            pytest.skip(f"chromium unavailable: {exc}")
        try:
            yield launched
        finally:
            launched.close()


@pytest.fixture
def base_url(tmp_path: Path):
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password=PASSWORD,
        host="127.0.0.1",
        port=0,
        workers=1,
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        srv.shutdown()
        srv.stop_background_worker()
        srv.server_close()


@pytest.fixture
def page(browser, base_url):
    """A logged-in, terms-accepted app page on a phone-sized viewport."""
    context = browser.new_context(
        viewport={"width": 412, "height": 915},
        reduced_motion="no-preference",
    )
    try:
        yield _sign_in(context, base_url)
    finally:
        context.close()


def _sign_in(context, base_url: str, *, android: bool = False):
    if android:
        # maybeShowFirstRunHelp() only auto-opens the tutorial inside the
        # native shell, so the first-run tests need the bridge MainActivity
        # injects. Must be installed before any script on the page runs.
        context.add_init_script("window.AndroidBridge = { isAvailable: () => true };")
    page = context.new_page()
    page.goto(base_url)
    page.fill("#login-password", PASSWORD)
    page.click("#login-btn")
    # First launch stops at the terms gate; accepting it calls setAuthed(true)
    # a second time, which is exactly the repeat the first-run guard has to
    # survive (see test_the_tutorial_does_not_reopen_itself_on_a_repeat_login).
    page.wait_for_selector("#terms-overlay:not(.hidden), #app:not(.hidden)")
    if page.locator("#terms-overlay:not(.hidden)").count():
        page.check("#terms-checkbox")
        page.click("#terms-accept-btn")
    page.wait_for_selector("#app:not(.hidden)")
    return page


def _wait_for_phase(page, phase: str, timeout: int = 15000) -> None:
    page.wait_for_function(f"() => {PHASE} === {phase!r}", timeout=timeout)


def test_the_written_guide_is_a_real_modal_over_the_app(page) -> None:
    """Regression: #help-guide-overlay had no overlay rules at all.

    Every other overlay in this page is `position: fixed; inset: 0`, but the
    guide only ever got `.card { max-width }`. It therefore rendered as an
    ordinary block at its DOM position - the app remained visible and
    scrollable beneath it, and its close button sat under the status bar.
    """
    page.click("#help-open-btn")
    page.click("#help-guide-btn")
    page.wait_for_selector("#help-guide-overlay:not(.hidden)")

    overlay = page.locator("#help-guide-overlay")
    assert overlay.evaluate("el => getComputedStyle(el).position") == "fixed"

    # It must cover the whole viewport, anchored at the top-left corner.
    box = overlay.bounding_box()
    viewport = page.viewport_size
    assert box is not None
    assert (round(box["x"]), round(box["y"])) == (0, 0)
    assert round(box["width"]) >= viewport["width"]
    assert round(box["height"]) >= viewport["height"]

    # ...and actually occlude the app: whatever sits at the centre of the
    # screen has to belong to the guide, not to the download form behind it.
    centre_is_inside_guide = page.evaluate(
        "([x, y]) => !!document.elementFromPoint(x, y)"
        ".closest('#help-guide-overlay')",
        [viewport["width"] // 2, viewport["height"] // 2],
    )
    assert centre_is_inside_guide

    # The page itself must not have grown a scrollbar - the pre-fix layout
    # stacked the guide *above* #app in flow, making the document taller.
    assert page.evaluate("document.documentElement.scrollHeight <= window.innerHeight + 1")

    # The close button is the specific thing that went off-screen: it must be
    # fully on screen, hit-testable, and actually close the guide.
    close_box = page.locator("#help-guide-close-btn").bounding_box()
    assert close_box is not None
    assert close_box["y"] >= 0
    assert close_box["y"] + close_box["height"] <= viewport["height"]
    page.click("#help-guide-close-btn", timeout=2000)
    assert page.locator("#help-guide-overlay.hidden").count() == 1


def test_a_spurious_visibilitychange_does_not_restart_the_tutorial(page) -> None:
    """Regression: the reported "always jumps back to the start" loop.

    The handler called play() on every visibilitychange, and play() always
    begins at scene 1. An Android WebView fires that event far more often
    than the "user backgrounded the app" case it was written for, so the
    animation could be yanked back to scene 1 before it ever reached scene 2.
    """
    page.click("#help-open-btn")
    _wait_for_phase(page, "share")  # scene 02 - past the first scene

    # Fire the event the WebView over-fires, with the tab still visible.
    for _ in range(3):
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(400)

    assert page.evaluate(PHASE) == "share", "a visible-tab visibilitychange restarted the run"

    # The run must still be live afterwards, not merely frozen on scene 2.
    _wait_for_phase(page, "format")


def test_backgrounding_pauses_and_returning_resumes_without_rewinding(page) -> None:
    """The genuine background/foreground case must still pause and resume."""
    page.click("#help-open-btn")
    _wait_for_phase(page, "share")

    # Real hide: timers are cleared, so the scene must not advance.
    page.evaluate(
        "Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});"
        "document.dispatchEvent(new Event('visibilitychange'));"
    )
    page.wait_for_timeout(1200)
    assert page.evaluate(PHASE) == "share", "the loop kept running while hidden"

    # Coming back resumes the loop rather than restarting it at scene 1.
    page.evaluate(
        "Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});"
        "document.dispatchEvent(new Event('visibilitychange'));"
    )
    _wait_for_phase(page, "share")
    _wait_for_phase(page, "format")


def test_reopening_a_closed_tutorial_starts_over_at_scene_one(page) -> None:
    page.click("#help-open-btn")
    _wait_for_phase(page, "format")  # scene 03

    page.click("#help-close-btn")
    assert page.locator("#help-overlay.hidden").count() == 1

    page.click("#help-open-btn")
    # Restart is synchronous in openHelp(), so scene 1 must be showing at once.
    assert page.evaluate(PHASE) == "source"


def test_opening_help_while_it_is_already_open_does_not_rewind_it(page) -> None:
    """The other half of the openHelp() guard.

    Reopening a *closed* tutorial restarts it (test above); a trigger arriving
    while it is already on screen must leave the current run alone.
    """
    page.click("#help-open-btn")
    _wait_for_phase(page, "share")

    page.evaluate("openHelp()")
    page.wait_for_timeout(300)

    assert page.evaluate(PHASE) == "share"


def test_player_first_home_does_not_auto_open_share_tutorial(browser, base_url) -> None:
    context = browser.new_context(
        viewport={"width": 412, "height": 915},
        reduced_motion="no-preference",
    )
    try:
        page = _sign_in(context, base_url, android=True)
        page.wait_for_timeout(500)
        assert page.locator("#help-overlay.hidden").count() == 1
    finally:
        context.close()


def test_repeat_login_keeps_share_tutorial_closed_on_player_first_home(browser, base_url) -> None:
    context = browser.new_context(
        viewport={"width": 412, "height": 915},
        reduced_motion="no-preference",
    )
    try:
        page = _sign_in(context, base_url, android=True)
        assert page.locator("#help-overlay.hidden").count() == 1
        page.evaluate("setAuthed(true)")
        page.evaluate("setAuthed(true)")
        page.wait_for_timeout(700)
        assert page.locator("#help-overlay.hidden").count() == 1
    finally:
        context.close()


def test_manually_opened_tutorial_does_not_reopen_after_dismissal(browser, base_url) -> None:
    context = browser.new_context(
        viewport={"width": 412, "height": 915},
        reduced_motion="no-preference",
    )
    try:
        page = _sign_in(context, base_url, android=True)
        page.click("#help-open-btn")
        page.wait_for_selector("#help-overlay:not(.hidden)")
        page.click("#help-close-btn")
        assert page.locator("#help-overlay.hidden").count() == 1

        page.evaluate("setAuthed(true)")
        page.wait_for_timeout(700)

        assert page.locator("#help-overlay.hidden").count() == 1, "the tutorial re-opened itself"
    finally:
        context.close()


def test_a_share_arriving_during_a_manually_opened_tutorial_reaches_a_clickable_picker(
    browser, base_url
) -> None:
    """A shared link must close a tutorial which the user opened manually.

    #help-overlay's z-index (57) sits above #share-format-overlay's (56), so
    the picker rendered *underneath* the tutorial - same dimmed background,
    easy to mistake for nothing having happened. On device this was worse
    than a visual glitch: the tutorial's own inert phone-mockup "format"
    scene carries its own "Video"/"Audio" labels, so the on-device smoke
    test's "tap whichever Video match sits lowest on screen" heuristic could
    land on that dead mockup button instead of the real one - the share
    never reached the queue at all.

    Playwright's click() mirrors that failure mode for free: it refuses to
    click an element another node is intercepting, so this fails exactly
    the way the on-device tap did if the fix regresses.
    """
    context = browser.new_context(
        viewport={"width": 412, "height": 915},
        reduced_motion="no-preference",
    )
    try:
        page = _sign_in(context, base_url, android=True)
        page.click("#help-open-btn")
        page.wait_for_selector("#help-overlay:not(.hidden)")
        _wait_for_phase(page, "share")  # tutorial genuinely mid-run, not just opened

        page.evaluate("window.onSharedUrl('https://example.com/clip.mp4')")

        assert page.locator("#help-overlay.hidden").count() == 1, (
            "the tutorial was still open once a share arrived"
        )
        page.wait_for_selector("#share-format-overlay:not(.hidden)")
        assert page.locator("#url-input").input_value() == "https://example.com/clip.mp4"

        # The real proof: an actual click must land on the picker's button,
        # not be swallowed by whatever the tutorial left behind.
        page.click("#share-format-video-btn", timeout=2000)
        assert page.locator("#share-format-overlay.hidden").count() == 1
    finally:
        context.close()
