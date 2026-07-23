"""Regression guards for release-critical GitHub Actions behavior."""

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
