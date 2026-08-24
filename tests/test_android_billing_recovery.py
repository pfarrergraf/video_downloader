from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_play_purchase_is_reconciled_on_foreground_resume() -> None:
    controller = (
        ROOT
        / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")
    activity = (
        ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt"
    ).read_text(encoding="utf-8")

    assert 'syncPurchases(reportMissingPurchase = false, event = "sync")' in controller
    assert "override fun refreshPurchases()" in controller
    assert "purchaseController.refreshPurchases()" in activity


def test_automatic_reconciliation_does_not_show_no_purchase_failure() -> None:
    controller = (
        ROOT
        / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")

    assert "purchases.isEmpty() && reportMissingPurchase" in controller
    assert "if (reportMissingPurchase)" in controller


def test_purchase_opens_play_flow_without_a_refund_history_cooldown() -> None:
    controller = (
        ROOT
        / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")

    purchase_body = controller.split("override fun purchase(activity: Activity)", 1)[1].split(
        "override fun restore()", 1
    )[0]
    assert "purchaseFlowInProgress" in purchase_body
    assert "loadProduct" in purchase_body
    assert "checkPurchaseEligibility" not in purchase_body
    assert "purchase_cooldown" not in purchase_body
    assert "checkOwnedBeforePurchase" not in controller


def test_already_owned_and_cancelled_results_are_not_generic_failures() -> None:
    controller = (
        ROOT
        / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")

    assert "ITEM_ALREADY_OWNED -> PurchaseFlowSignal.ITEM_ALREADY_OWNED" in controller
    assert 'errorJson("restoring_purchase"' in controller
    assert "remainingEmptyRetries = 2" in controller
    assert "500L" in controller
    assert "USER_CANCELED -> PurchaseFlowSignal.USER_CANCELLED" in controller
    assert 'errorJson("purchase_cancelled"' in controller


def test_only_server_revoked_purchase_is_consumed_for_repurchase() -> None:
    controller = (
        ROOT / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")
    server_result = controller.split("private fun onServerResult", 1)[1].split(
        "private fun consumeRevokedPurchase", 1
    )[0]
    assert 'if (result.optBoolean("revoked")) {' in server_result
    assert "verifiedToken?.let(::consumeRevokedPurchase)" in server_result
    assert "consumeRevokedPurchase" not in server_result.split(
        'if (result.optBoolean("revoked")) {', 1
    )[0]
    consume = controller.split("private fun consumeRevokedPurchase", 1)[1].split(
        "private fun loadProduct", 1
    )[0]
    assert "billingClient.consumeAsync" in consume
    assert "ITEM_NOT_OWNED" in consume
    assert 'result.remove("_purchase_token")' in server_result
    assert "lastVerifiedPurchaseToken" not in controller


def test_native_result_waits_for_authenticated_web_callback() -> None:
    activity = (
        ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt"
    ).read_text(encoding="utf-8")
    html = (ROOT / "video_downloader/web/static/index.html").read_text(encoding="utf-8")

    assert "pendingEntitlementResult" in activity
    assert "entitlementDeliveryInFlight" in activity
    assert "fun onEntitlementUiReady()" in activity
    assert "window.AndroidBridge.onEntitlementUiReady();" in html


def test_native_and_python_share_one_stable_android_identity() -> None:
    native_api = (
        ROOT / "android/app/src/main/java/de/classydl/app/EntitlementApi.kt"
    ).read_text(encoding="utf-8")
    runtime = (
        ROOT / "android/app/src/main/java/de/classydl/app/ServerRuntime.kt"
    ).read_text(encoding="utf-8")
    python_entry = (ROOT / "video_downloader/android_entry.py").read_text(encoding="utf-8")

    assert "InstallIdentity.getOrCreate(appContext)" in native_api
    assert "InstallIdentity.getOrCreate(appContext)" in runtime
    assert "license_device_id" in python_entry


def test_entitlement_api_supports_result_specific_callbacks() -> None:
    native_api = (
        ROOT / "android/app/src/main/java/de/classydl/app/EntitlementApi.kt"
    ).read_text(encoding="utf-8")

    assert "callback: ((JSONObject) -> Unit)? = null" in native_api
    assert 'parsed.put("status", status)' in native_api
    assert "if (callback != null) mainHandler.post { callback(result) }" in native_api


def test_app_has_no_first_party_refund_request_flow() -> None:
    controller = (
        ROOT / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")
    direct = (
        ROOT / "android/app/src/direct/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")
    interface = (
        ROOT / "android/app/src/main/java/de/classydl/app/PurchaseController.kt"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "android/app/src/main/java/de/classydl/app/EntitlementApi.kt"
    ).read_text(encoding="utf-8")
    activity = (
        ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt"
    ).read_text(encoding="utf-8")
    web = (ROOT / "video_downloader/web/static/index.html").read_text(encoding="utf-8")

    combined = "\n".join((controller, direct, interface, api, activity, web))
    assert "requestRefund" not in combined
    assert "requestPlayRefund" not in combined
    assert '"/api/play/refunds/request"' not in combined
    assert 'id="play-refund-overlay"' not in combined
