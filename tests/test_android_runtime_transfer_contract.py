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
    assert 'failClosed("foreground promotion rejected")' in service
    assert 'failClosed("foreground re-promotion rejected")' in service
    on_destroy = service.split("override fun onDestroy()", 1)[1].split("override fun onTaskRemoved", 1)[0]
    assert "failClosed" in on_destroy


def test_web_and_native_producers_use_transfer_coordinator() -> None:
    activity = _read("android/app/src/main/java/de/classydl/app/MainActivity.kt")
    local = _read("android/app/src/main/java/de/classydl/app/LocalApiClient.kt")
    web = _read("video_downloader/web/static/index.html")
    assert "TransferCoordinator.beginTransfer(this@MainActivity)" in activity
    assert "TransferCoordinator.beginTransfer(context)" in local
    assert "window.AndroidBridge.beginTransfer()" in web
    assert "window.AndroidBridge.completeTransfer(transfer, queued)" in web
    retry = web.split("// One-tap retry", 1)[1].split("li.appendChild(retryBtn)", 1)[0]
    assert "beginNativeTransfer()" in retry
    assert "completeNativeTransfer(nativeTransfer, queued)" in retry


def test_server_runtime_is_single_flight_and_retryable() -> None:
    runtime = _read("android/app/src/main/java/de/classydl/app/ServerRuntime.kt")
    assert "enum class State { STOPPED, STARTING, READY, FAILED }" in runtime
    assert "synchronized(lock)" in runtime
    assert "if (state == State.STARTING || state == State.READY) return" in runtime
    assert "CopyOnWriteArraySet<Listener>" in runtime


def test_transfer_service_start_failures_clean_up_and_fail_closed() -> None:
    coordinator = _read("android/app/src/main/java/de/classydl/app/TransferCoordinator.kt")
    begin = coordinator.split("fun beginTransfer", 1)[1].split("fun onForegroundConfirmed", 1)[0]
    complete = coordinator.split("fun completeTransfer", 1)[1]
    assert "try {" in begin and "ContextCompat.startForegroundService" in begin
    assert "foregroundConfirmations.remove(id)" in begin
    assert "ServerRuntime.setExecutionEnabled(false)" in begin
    assert "try {" in complete and "context.startService(intent)" in complete
    assert "ServerRuntime.cancelActiveTransfers()" in complete


def test_stale_native_result_cannot_resurrect_after_clear_tombstone() -> None:
    coordinator = _read("android/app/src/main/java/de/classydl/app/EntitlementCoordinator.kt")
    api = _read("android/app/src/main/java/de/classydl/app/EntitlementApi.kt")
    activity = _read("android/app/src/main/java/de/classydl/app/MainActivity.kt")
    play = _read("android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt")
    verified = coordinator.split("fun applyVerifiedResult", 1)[1].split(
        "fun applyRevokedResult", 1
    )[0]
    assert "current.revision > requestEpoch" in verified
    assert "return@synchronized false" in verified
    assert 'parsed.put("_entitlement_epoch", entitlementEpoch)' in api
    assert "EntitlementCoordinator.applyVerifiedResult(this, key, requestEpoch)" in activity
    assert "EntitlementCoordinator.applyVerifiedResult(appContext, licenseKey, requestEpoch)" in play
