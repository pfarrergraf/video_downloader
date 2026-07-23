"""Regression guards for release-critical GitHub Actions behavior."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_codeql_analyzes_only_declared_interpreted_languages() -> None:
    workflow = _workflow("codeql.yml")
    assert "languages: ${{ matrix.language }}" in workflow
    assert "build-mode: none" in workflow
    assert "codeql-action/autobuild@" not in workflow
    assert "codeql-action/init@" in workflow
    assert "codeql-action/analyze@" in workflow
    assert "# v4" in workflow


def test_android_ci_compiles_play_billing_flavor() -> None:
    workflow = _workflow("android-build.yml")
    assert ":app:assembleDirectDebug" in workflow
    assert ":app:compilePlayDebugKotlin" in workflow


def test_android_release_checks_complete_signing_configuration() -> None:
    workflow = _workflow("android-release.yml")
    required_names = (
        "ANDROID_APP_SIGNING_KEYSTORE_BASE64",
        "ANDROID_APP_SIGNING_KEYSTORE_PASSWORD",
        "ANDROID_APP_SIGNING_KEY_ALIAS",
        "ANDROID_APP_SIGNING_KEY_PASSWORD",
        "ANDROID_APP_SIGNING_CERT_SHA256",
        "ANDROID_UPLOAD_KEYSTORE_BASE64",
        "ANDROID_UPLOAD_KEYSTORE_PASSWORD",
        "ANDROID_UPLOAD_KEY_ALIAS",
        "ANDROID_UPLOAD_KEY_PASSWORD",
        "ANDROID_UPLOAD_CERT_SHA256",
    )
    for name in required_names:
        assert workflow.count(name) >= 2, name
    assert r"^v[0-9]+\.[0-9]+\.[0-9]+$" in workflow
    assert "cache-disabled: true" in workflow


def test_play_reconciliation_waits_for_backend_enablement() -> None:
    workflow = _workflow("google-play-reconciliation.yml")
    assert "if: vars.PLAY_BACKEND_CONFIGURED == 'true'" in workflow


def test_checkout_credentials_are_not_persisted() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        workflow = path.read_text(encoding="utf-8")
        checkout_count = workflow.count("uses: actions/checkout@")
        assert workflow.count("persist-credentials: false") == checkout_count, path.name


def _load_ui_target_module():
    path = ROOT / ".github" / "scripts" / "find_android_ui_target.py"
    spec = importlib.util.spec_from_file_location("find_android_ui_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_share_intent_smoke_test_ignores_unrelated_launcher_anr() -> None:
    module = _load_ui_target_module()
    xml = """<hierarchy>
      <node text="Pixel Launcher isn't responding"
            resource-id="android:id/alertTitle" bounds="[0,0][1,1]" />
      <node text="Close app" resource-id="android:id/aerr_close"
            bounds="[70,1170][1010,1296]" />
    </hierarchy>"""
    assert module.find_target(xml) == "DISMISS 540 1233"


def test_share_intent_smoke_test_selects_lower_video_picker_button() -> None:
    module = _load_ui_target_module()
    xml = """<hierarchy>
      <node text="Video" bounds="[10,100][110,200]" />
      <node text="Video format" bounds="[20,800][220,1000]" />
    </hierarchy>"""
    assert module.find_target(xml) == "120 900"
