"""Regression guards for Android foreground-download notification cleanup.

History: the service originally kept the "Downloads running" notification up
for ~30 idle ticks (IDLE_TICKS_BEFORE_STOP, 1s cadence) before leaving
foreground - real tester feedback called that "still says downloading when
it's done". Dropping foreground on the very first empty snapshot fixed that,
but broke a different guarantee: a foreground service's OOM-killer immunity
requires a visible notification, there is no "foreground but invisible", so
for the entire time between the queue emptying and the notification being
removed the process had zero protection against being killed while
backgrounded (caught by .github/scripts/background_survival_test.sh: the
embedded Python server was dead within 30s of backgrounding). The fix here
keeps both real: the notification text changes to an honest "done" state
immediately (no more stale "downloading"), but the service stays a genuine,
protected foreground service for IDLE_GRACE_MS afterwards.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "android/app/src/main/java/de/classydl/app/DownloadService.kt"
STRINGS_EN = ROOT / "android/app/src/main/res/values/strings.xml"
STRINGS_DE = ROOT / "android/app/src/main/res/values-de/strings.xml"


def test_empty_queue_never_reintroduces_a_tick_based_idle_counter() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert "IDLE_TICKS_BEFORE_STOP" not in source
    assert "stopForeground(STOP_FOREGROUND_REMOVE)" in source
    # Normal idle cleanup retains the service; stopSelf is reserved for the
    # mandatory Android 15+ foreground-service timeout callback.
    idle_shutdown = source.split("private val idleShutdownRunnable = Runnable {", 1)[1].split("}\n", 1)[0]
    assert "stopSelf" not in idle_shutdown


def test_queue_emptying_immediately_shows_an_honest_idle_notification() -> None:
    # The actual tester complaint was about the *text* ("still downloading"),
    # not the notification's mere existence - so the swap to notif_idle must
    # happen on the very same snapshot the queue empties on, unconditionally,
    # not after any delay.
    source = SERVICE.read_text(encoding="utf-8")
    idle_branch = source.split("} else if (inForeground", 1)[1].split("\n    }\n", 1)[0]

    assert "getString(R.string.notif_idle)" in idle_branch
    assert "ongoing = false" in idle_branch
    assert "notificationManager().notify(" in idle_branch


def test_leaving_foreground_is_delayed_by_a_time_based_grace_period() -> None:
    # Time-based (Handler.postDelayed), not tick-based - handleSnapshot() runs
    # on every ~1s publisher poll whether or not the queue changed, so a tick
    # counter would silently stop advancing the moment the queue goes idle
    # (nothing to count), which is exactly how the old logic gave stale
    # coverage. IDLE_GRACE_MS must comfortably exceed
    # background_survival_test.sh's 30s backgrounding sleep, or CI stays red.
    source = SERVICE.read_text(encoding="utf-8")

    assert "private const val IDLE_GRACE_MS = 45_000L" in source
    assert "handler.postDelayed(idleShutdownRunnable, IDLE_GRACE_MS)" in source

    idle_shutdown_runnable = source.split("private val idleShutdownRunnable = Runnable {", 1)[1].split(
        "}\n", 1
    )[0]
    assert "stopForeground(STOP_FOREGROUND_REMOVE)" in idle_shutdown_runnable
    assert "inForeground = false" in idle_shutdown_runnable


def test_new_work_during_the_grace_period_cancels_the_pending_drop() -> None:
    # Without this, a download starting seconds after the last one finished
    # would still get yanked out of foreground when the earlier idle timer's
    # postDelayed eventually fires - it doesn't know a new download exists.
    source = SERVICE.read_text(encoding="utf-8")
    active_branch = source.split("if (activeCount > 0) {", 1)[1].split("\n            }\n", 1)[0]

    assert "if (idleShutdownScheduled)" in active_branch
    assert "handler.removeCallbacks(idleShutdownRunnable)" in active_branch
    assert "idleShutdownScheduled = false" in active_branch


def test_idle_transition_is_guarded_against_the_continuous_publisher_poll() -> None:
    # android_entry.py's publisher loop calls onJobsChanged() every ~1s
    # unconditionally, active queue or not - without idleShutdownScheduled in
    # the branch condition, every one of those idle ticks would re-notify()
    # and re-postDelayed(), perpetually pushing the deadline out and
    # reproducing the exact bug this fix closes.
    source = SERVICE.read_text(encoding="utf-8")
    assert "else if (inForeground && !idleShutdownScheduled) {" in source


def test_pending_idle_shutdown_is_cancelled_on_service_destroy() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    on_destroy = source.split("override fun onDestroy() {", 1)[1].split("}\n", 1)[0]
    assert "handler.removeCallbacks(idleShutdownRunnable)" in on_destroy


def test_notif_idle_string_present_in_both_locales() -> None:
    for path in (STRINGS_EN, STRINGS_DE):
        assert '<string name="notif_idle">' in path.read_text(encoding="utf-8"), (
            f"missing notif_idle in {path}"
        )


def test_foreground_promotion_survives_a_background_start_restriction() -> None:
    # Android 12+ can throw ForegroundServiceStartNotAllowedException when a
    # service tries to promote itself to foreground while the app is in the
    # background - a real path here: handleSnapshot() runs continuously on
    # the Python publisher thread with no Activity in the call stack, and a
    # queued job's automatic retry-after-failure can land after IDLE_GRACE_MS
    # has already dropped foreground status and the user has since
    # backgrounded the app. Android's own guidance is to catch this, not to
    # try to predict it, so goForeground()'s startForeground() calls must be
    # wrapped rather than left to crash the whole process.
    source = SERVICE.read_text(encoding="utf-8")
    go_foreground = source.split("private fun goForeground(text: String) {", 1)[1].split(
        "\n    }\n", 1
    )[0]

    assert "try {" in go_foreground
    assert "catch (e: IllegalStateException) {" in go_foreground
    # inForeground must only flip true on the success path, inside the try -
    # otherwise a caught failure would leave the service believing it is
    # foreground-protected when it is not.
    success_path = go_foreground.split("try {", 1)[1].split("} catch", 1)[0]
    assert "inForeground = true" in success_path
    assert "inForeground = true" not in go_foreground.split("} catch", 1)[1]


def test_android_15_data_sync_timeout_cancels_work_and_stops_service() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    timeout = source.split("override fun onTimeout(startId: Int, fgsType: Int) {", 1)[1].split(
        "\n    }\n", 1
    )[0]
    assert 'callAttr("cancel_active_for_system_timeout")' in timeout
    assert "stopForeground(STOP_FOREGROUND_REMOVE)" in timeout
    assert "stopSelf(startId)" in timeout


def test_completed_notification_uses_explicit_media_mime_and_chooser() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert "MediaMimeTypes.forFile(File(path))" in source
    assert '?: "*/*"' not in source
    assert "Intent.createChooser(view, null)" in source
