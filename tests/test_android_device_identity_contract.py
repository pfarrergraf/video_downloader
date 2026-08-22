from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_android_license_identity_is_reinstall_stable_and_locally_hashed() -> None:
    identity = (
        ROOT / "android/app/src/main/java/de/classydl/app/InstallIdentity.kt"
    ).read_text(encoding="utf-8")

    assert "Settings.Secure.ANDROID_ID" in identity
    assert 'DEVICE_NAMESPACE = "downloadthat-license-device-v1:"' in identity
    assert 'MessageDigest.getInstance("SHA-256")' in identity
    assert "return sha256Hex(DEVICE_NAMESPACE + androidId)" in identity
    assert "legacyForMigration" not in identity


def test_all_android_entitlement_paths_share_the_stable_identity() -> None:
    api = (
        ROOT / "android/app/src/main/java/de/classydl/app/EntitlementApi.kt"
    ).read_text(encoding="utf-8")
    runtime = (
        ROOT / "android/app/src/main/java/de/classydl/app/ServerRuntime.kt"
    ).read_text(encoding="utf-8")
    controller = (
        ROOT / "android/app/src/play/java/de/classydl/app/PurchaseControllerFactory.kt"
    ).read_text(encoding="utf-8")

    assert "InstallIdentity.getOrCreate(appContext)" in api
    assert "InstallIdentity.getOrCreate(appContext)" in runtime
    assert "InstallIdentity.getOrCreate(context)" in controller
    assert '.put("device_id_scheme", DEVICE_ID_SCHEME)' in api
    assert '.put("app_version", BuildConfig.VERSION_NAME)' in api


def test_python_license_manager_does_not_reintroduce_legacy_android_install_id() -> None:
    licensing = (ROOT / "video_downloader/licensing.py").read_text(encoding="utf-8")

    assert 'ANDROID_DEVICE_ID_SCHEME = "android-scoped-v1"' in licensing
    assert 'payload["device_id_scheme"] = self._device_id_scheme' in licensing
    assert "legacy_device_id" not in licensing
    assert "_legacy_device_id" not in licensing


def test_verified_google_play_purchase_is_the_only_automatic_slot_transfer_path() -> None:
    validation = (
        ROOT / "pro/website/functions/_license_validation.js"
    ).read_text(encoding="utf-8")
    verify = (
        ROOT / "pro/website/functions/api/play/purchases/verify.js"
    ).read_text(encoding="utf-8")

    assert "export async function claimVerifiedDeviceSlot" in validation
    assert "claimVerifiedDeviceSlot(env" in verify
    assert "verifyAndApplyPlayPurchase" in verify
    assert verify.index("verifyAndApplyPlayPurchase") < verify.index("claimVerifiedDeviceSlot(env")
    assert "claimVerifiedDeviceSlot" not in (
        ROOT / "pro/website/functions/api/license/validate.js"
    ).read_text(encoding="utf-8")


def test_verified_entitlement_forces_embedded_queue_license_refresh() -> None:
    api = (
        ROOT / "android/app/src/main/java/de/classydl/app/EntitlementApi.kt"
    ).read_text(encoding="utf-8")
    local = (
        ROOT / "android/app/src/main/java/de/classydl/app/LocalApiClient.kt"
    ).read_text(encoding="utf-8")

    assert "syncEmbeddedLicenseIfActive(parsed)" in api
    assert "LocalApiClient.syncLicense(appContext, key)" in api
    assert "fun syncLicense(context: Context, licenseKey: String): Boolean" in local
    assert '"POST",\n            "/api/license"' in local
