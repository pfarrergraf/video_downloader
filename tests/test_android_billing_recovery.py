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

    assert "syncPurchases(reportMissingPurchase = false)" in controller
    assert "override fun refreshPurchases()" in controller
    assert "purchaseController.refreshPurchases()" in activity


def test_automatic_reconciliation_does_not_show_no_purchase_failure() -> None:
    controller = (
        ROOT
        / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")

    assert "purchases.isEmpty() && reportMissingPurchase" in controller
    assert "if (reportMissingPurchase)" in controller


def test_purchase_checks_owned_items_before_opening_a_new_flow() -> None:
    controller = (
        ROOT
        / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")

    purchase_body = controller.split("override fun purchase(activity: Activity)", 1)[1].split(
        "override fun restore()", 1
    )[0]
    assert "purchaseFlowInProgress" in purchase_body
    assert "checkOwnedBeforePurchase(activity)" in purchase_body
    owned_check = controller.split("private fun checkOwnedBeforePurchase", 1)[1].split(
        "private fun launchPurchase", 1
    )[0]
    assert owned_check.index("queryOwnedPurchases") < owned_check.index("loadProduct")
    assert "purchases.forEach(::handlePurchase)" in owned_check


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


def test_native_result_waits_for_authenticated_web_callback() -> None:
    activity = (
        ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt"
    ).read_text(encoding="utf-8")
    html = (ROOT / "video_downloader/web/static/index.html").read_text(encoding="utf-8")

    assert "pendingEntitlementResult" in activity
    assert "entitlementDeliveryInFlight" in activity
    assert "fun onEntitlementUiReady()" in activity
    assert "window.AndroidBridge.onEntitlementUiReady();" in html


def test_native_and_python_share_one_install_identity() -> None:
    native_api = (
        ROOT / "android/app/src/main/java/de/classydl/app/EntitlementApi.kt"
    ).read_text(encoding="utf-8")
    runtime = (
        ROOT / "android/app/src/main/java/de/classydl/app/ServerRuntime.kt"
    ).read_text(encoding="utf-8")
    python_entry = (ROOT / "video_downloader/android_entry.py").read_text(encoding="utf-8")

    assert "InstallIdentity.getOrCreate(context)" in native_api
    assert "InstallIdentity.getOrCreate(appContext)" in runtime
    assert "license_device_id" in python_entry


def test_play_refund_flow_stays_native_and_purchase_token_bound() -> None:
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

    assert "fun requestRefund(reason: String)" in interface
    assert "override fun requestRefund(reason: String)" in controller
    assert "override fun requestRefund(reason: String)" in direct
    assert "api.requestRefund(purchase.purchaseToken, reason)" in controller
    assert '"/api/play/refunds/request"' in api
    assert '.put("purchase_token", token)' in api
    assert '.put("device_id", deviceId)' in api
    assert "fun requestPlayRefund(reason: String)" in activity
    assert 'id="play-refund-overlay"' in web
    assert "if (!window.confirm(" not in web
