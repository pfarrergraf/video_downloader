from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_opening_app_starts_runtime_without_download_service() -> None:
    activity = _read("android/app/src/main/java/de/classydl/app/MainActivity.kt")
    on_create = activity.split("override fun onCreate", 1)[1].split("override fun onResume", 1)[0]
    assert "ServerRuntime.ensureStarted(applicationContext)" in on_create
    assert "startDownloadService()" not in on_create


def test_transfer_foreground_precedes_python_execution_gate() -> None:
    service = _read("android/app/src/main/java/de/classydl/app/DownloadService.kt")
    coordinator = _read("android/app/src/main/java/de/classydl/app/TransferCoordinator.kt")
    assert coordinator.index("confirmation.await") < coordinator.index("EntitlementCoordinator.applyDesired")
    assert coordinator.index("EntitlementCoordinator.applyDesired") < coordinator.index(
        "ServerRuntime.setExecutionEnabled(true)"
    )
    assert "TransferCoordinator::onForegroundConfirmed" in service
    assert "ServerRuntime.setExecutionEnabled(false)" in service
    assert "stopSelf()" in service


def test_web_and_native_producers_use_transfer_coordinator() -> None:
    activity = _read("android/app/src/main/java/de/classydl/app/MainActivity.kt")
    local = _read("android/app/src/main/java/de/classydl/app/LocalApiClient.kt")
    web = _read("video_downloader/web/static/index.html")
    assert "TransferCoordinator.beginTransfer(this@MainActivity)" in activity
    assert "TransferCoordinator.beginTransfer(context)" in local
    assert "window.AndroidBridge.beginTransfer()" in web
    assert "window.AndroidBridge.completeTransfer(nativeTransfer, queued)" in web


def test_server_runtime_is_single_flight_and_retryable() -> None:
    runtime = _read("android/app/src/main/java/de/classydl/app/ServerRuntime.kt")
    assert "enum class State { STOPPED, STARTING, READY, FAILED }" in runtime
    assert "synchronized(lock)" in runtime
    assert "if (state == State.STARTING || state == State.READY) return" in runtime
    assert "CopyOnWriteArraySet<Listener>" in runtime
