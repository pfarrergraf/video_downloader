"""Browser-level regression coverage for the considerate Play rating prompt."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from video_downloader.queue_store import QueueStore
from video_downloader.web.server import create_server

sync_api = pytest.importorskip("playwright.sync_api")

PASSWORD = "rating-prompt-test"
STATE_KEY = "downloadthat:review-prompt:v1"


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium unavailable: {exc}")
        try:
            yield launched
        finally:
            launched.close()


@pytest.fixture
def base_url(tmp_path: Path):
    store = QueueStore(tmp_path / "state.db")
    store.init()
    server = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password=PASSWORD,
        host="127.0.0.1",
        port=0,
        workers=1,
        app_version="review-test-1",
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.stop_background_worker()
        server.server_close()


@pytest.fixture
def page(browser, base_url):
    context = browser.new_context(viewport={"width": 412, "height": 915})
    context.add_init_script(
        """
        (() => {
          try { localStorage.setItem('downloadthat:first-run-help:v1', '1'); } catch (_) {}
          window.__playStoreOpens = 0;
          window.AndroidBridge = {
            isAvailable: () => true,
            openPlayStore: () => { window.__playStoreOpens += 1; },
          };
        })();
        """
    )
    tab = context.new_page()
    tab.goto(base_url)
    tab.fill("#login-password", PASSWORD)
    tab.click("#login-btn")
    tab.wait_for_selector("#terms-overlay:not(.hidden), #app:not(.hidden)")
    if tab.locator("#terms-overlay:not(.hidden)").count():
        tab.check("#terms-checkbox")
        tab.click("#terms-accept-btn")
    tab.wait_for_selector("#app:not(.hidden)")
    if tab.locator("#help-overlay:not(.hidden)").count():
        tab.click("#help-close-btn")
    tab.wait_for_function("reviewPromptVersion === 'review-test-1'")
    tab.wait_for_function("reviewQueueBaselineReady === true")
    try:
        yield tab
    finally:
        context.close()


def _job(job_id: int, status: str, *, error: str | None = None, with_file: bool = True) -> dict:
    files = []
    if status == "completed" and with_file:
        files = [
            {
                "filename": f"clip-{job_id}.mp4",
                "download_url": f"/downloads/{job_id}/clip-{job_id}.mp4",
            }
        ]
    return {
        "id": job_id,
        "created_at": f"2026-08-07T12:00:{job_id:02d}+00:00",
        "source": f"https://example.com/{job_id}",
        "status": status,
        "error": error,
        "error_code": "unknown" if error else None,
        "files": files,
        "downloaded_bytes": 0,
        "total_bytes": None,
    }


def _render(page, jobs: list[dict]) -> None:
    page.evaluate("jobs => renderJobs(jobs)", jobs)


def _state(page) -> dict:
    raw = page.evaluate("key => localStorage.getItem(key)", STATE_KEY)
    return json.loads(raw)


def _visible(page) -> bool:
    return page.locator("#review-prompt-overlay:not(.hidden)").count() == 1


def test_existing_history_is_only_a_baseline_and_never_opens_on_startup(page) -> None:
    page.evaluate(
        """
        () => {
          reviewQueueBaselineReady = false;
          observedReviewJobs.clear();
          countedReviewJobs.clear();
        }
        """
    )
    _render(page, [_job(1, "completed"), _job(2, "completed")])

    assert not _visible(page)
    assert _state(page)["successes"] == 0


def test_two_new_clean_successes_open_the_prompt_once(page) -> None:
    first = _job(1, "completed")
    second = _job(2, "completed")

    _render(page, [first])
    assert not _visible(page)
    _render(page, [first, second])

    assert _visible(page)
    assert _state(page)["successes"] == 2
    assert _state(page)["failures"] == 0
    assert _state(page)["decision"] == "shown"


def test_prompt_waits_until_no_download_is_active(page) -> None:
    first = _job(1, "completed")
    second_active = _job(2, "in_progress", with_file=False)

    _render(page, [first, second_active])
    assert not _visible(page)

    _render(page, [first, _job(2, "completed")])
    assert _visible(page)


def test_prompt_waits_for_an_existing_modal_to_close(page) -> None:
    page.click("#settings-open-btn")
    page.wait_for_selector("#settings-overlay:not(.hidden)")

    _render(page, [_job(1, "completed")])
    _render(page, [_job(1, "completed"), _job(2, "completed")])
    assert not _visible(page)

    page.click("#settings-close-btn")
    page.wait_for_selector("#review-prompt-overlay:not(.hidden)")
    assert _visible(page)


@pytest.mark.parametrize(
    "bad_job",
    [
        _job(2, "failed", error="network failed", with_file=False),
        _job(2, "completed", error="MP3 conversion failed"),
        _job(2, "completed", with_file=False),
    ],
)
def test_failure_or_qualified_completion_blocks_later_prompts(page, bad_job: dict) -> None:
    first = _job(1, "completed")
    _render(page, [first])
    _render(page, [first, bad_job])
    _render(page, [first, bad_job, _job(3, "completed"), _job(4, "completed")])

    assert not _visible(page)
    assert _state(page)["failures"] == 1


def test_dismissal_is_persisted_and_additional_successes_do_not_nag(page) -> None:
    _render(page, [_job(1, "completed")])
    _render(page, [_job(1, "completed"), _job(2, "completed")])
    assert _visible(page)

    page.click("#review-prompt-dismiss-btn")
    assert not _visible(page)
    assert _state(page)["decision"] == "dismissed"

    _render(page, [_job(1, "completed"), _job(2, "completed"), _job(3, "completed")])
    assert not _visible(page)

    page.reload()
    page.wait_for_selector("#app:not(.hidden)")
    page.wait_for_function("reviewPromptVersion === 'review-test-1'")
    page.wait_for_function("reviewQueueBaselineReady === true")
    _render(page, [_job(10, "completed")])
    _render(page, [_job(10, "completed"), _job(11, "completed")])

    assert not _visible(page)
    assert _state(page)["decision"] == "dismissed"


def test_rating_action_uses_the_existing_native_play_store_route(page) -> None:
    _render(page, [_job(1, "completed")])
    _render(page, [_job(1, "completed"), _job(2, "completed")])
    assert _visible(page)

    page.click("#review-prompt-rate-btn")

    assert page.evaluate("window.__playStoreOpens") == 1
    assert _state(page)["decision"] == "opened"
    assert not _visible(page)


def test_german_prompt_reuses_the_localized_google_play_copy(page) -> None:
    page.evaluate("setLanguage('de')")
    assert page.locator("#review-prompt-title").inner_text() == "Du bist zufrieden mit DownloadThat?"
    _render(page, [_job(1, "completed")])
    _render(page, [_job(1, "completed"), _job(2, "completed")])

    assert page.locator("#review-prompt-title").inner_text() == "Du bist zufrieden mit DownloadThat?"
