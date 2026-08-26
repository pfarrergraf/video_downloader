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
    assert "api-level: [34, 35]" in workflow
    assert "api-level: ${{ matrix.api-level }}" in workflow


def test_android_release_checks_existing_app_and_upload_signing_configuration() -> None:
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
    assert "select_android_candidate_version.py" in workflow
    assert "assembleDirectRelease" in workflow
    assert "bundlePlayRelease" in workflow
    assert "check_android_release_artifacts.sh" in workflow
    # The build-tools version must stay pinned: an unpinned "newest installed"
    # lookup silently moved apksigner 36.0.0 -> 37.0.0 and broke cert parsing.
    assert '"$SDKMANAGER" --install "build-tools;36.0.0"' in workflow
    assert 'echo "$ANDROID_HOME/build-tools/36.0.0" >> "$GITHUB_PATH"' in workflow
    assert "find \"$ANDROID_HOME/build-tools\"" not in workflow
    # Cert parsing must not hard-code the "Signer #1" label or field position.
    assert "/Signer #1 certificate SHA-256 digest/{print $2; exit}" not in workflow
    assert "/certificate SHA-256 digest/{print $NF; exit}" in workflow
    assert "cache-disabled: true" in workflow


def test_apksigner_cert_parsing_survives_build_tools_label_changes() -> None:
    script = (ROOT / ".github" / "scripts" / "check_android_release_artifacts.sh").read_text(
        encoding="utf-8"
    )
    assert "/Signer #1 certificate SHA-256 digest/{print $2; exit}" not in script
    assert "/certificate SHA-256 digest/{print $NF; exit}" in script


def test_android_candidate_and_promotion_are_separate_exact_artifact_workflows() -> None:
    candidate = _workflow("android-release.yml")
    promotion = _workflow("android-promote-candidate.yml")
    assert "name: Android candidate build" in candidate
    assert "candidate-provenance.json" in candidate
    assert "--track internal" not in candidate
    assert "run-id: ${{ inputs.candidate_run_id }}" in promotion
    assert "--expected-version-code" in promotion
    assert "--track internal" in promotion
    assert "gradle " not in promotion.lower()
    assert "changesInReviewBehavior=ERROR_IF_IN_REVIEW" in (
        ROOT / "scripts/upload_google_play.mjs"
    ).read_text(encoding="utf-8")


def test_internal_app_sharing_is_isolated_from_release_signing() -> None:
    """The demo channel must stay incapable of signing or publishing a release.

    Internal app sharing re-signs every upload with Google's own key, so this
    workflow needs no signing secret. If one ever appears here, the throwaway
    channel has gained the ability to produce something that looks like a real
    artifact - which is exactly the confusion
    docs/ANDROID_PUBLISHING_CHANNELS_AND_KEYS.md exists to prevent.
    """
    workflow = _workflow("android-internal-sharing.yml")
    # Matches how a signing secret can actually enter a workflow. The bare
    # names may still appear in comments explaining what is deliberately absent.
    for forbidden in ("secrets.ANDROID_", "assembleDirectRelease"):
        assert forbidden not in workflow, forbidden
    # No track, no edit, no promotion: the only Play call is the sharing upload.
    assert "--internal-app-sharing true" in workflow
    assert "--track" not in workflow
    assert "--expected-version-code" not in workflow
    assert "bundlePlayRelease" in workflow
    # Public repo: the link must not be printed unless explicitly opted in.
    assert "if: inputs.share_via_api" in workflow
    assert "default: false" in workflow
    # A throwaway key, generated per run and never stored.
    assert "keytool -genkeypair" in workflow
    assert "jarsigner -verify" in workflow


def test_publishing_channel_doc_covers_every_channel_and_key() -> None:
    doc = (ROOT / "docs" / "ANDROID_PUBLISHING_CHANNELS_AND_KEYS.md").read_text(encoding="utf-8")
    for channel in ("android-release.yml", "android-promote-candidate.yml", "android-internal-sharing.yml"):
        assert channel in doc, channel
    for key in ("App-signing key", "Upload key", "Internal app sharing key", "Throwaway key"):
        assert key in doc, key
    # The two facts most likely to be re-derived wrongly by a future session.
    assert "cannot upgrade over each other" in doc
    assert "Never rotate or re-upload a production signing key" in doc
    # CLAUDE.md must point at it, since that is what gets read first.
    assert "docs/ANDROID_PUBLISHING_CHANNELS_AND_KEYS.md" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_play_reconciliation_waits_for_backend_enablement() -> None:
    workflow = _workflow("google-play-reconciliation.yml")
    assert "if: vars.PLAY_BACKEND_CONFIGURED == 'true'" in workflow


def test_commerce_preflight_is_stripe_free_and_exports_d1_read_only() -> None:
    workflow = _workflow("commerce-decommission-preflight.yml")
    assert "STRIPE_TEST_SECRET_KEY" not in workflow
    assert "export_stripe_test_evidence.py" not in workflow
    assert "d1 export downloadthat-licenses --remote" in workflow
    assert "d1 migrations apply" not in workflow


def test_owner_approved_website_dispatch_targets_pages_production() -> None:
    workflow = _workflow("deploy-pro-website.yml")
    assert "pages deploy . --project-name=downloadthat --branch=master" in workflow
    assert 'h.mode !== "play_backend"' in workflow
    assert "store/apps/details?id=de.classydl.app" in workflow


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


def test_share_intent_smoke_test_retries_transient_restart_responses() -> None:
    script = (ROOT / ".github" / "scripts" / "share_intent_test.sh").read_text(
        encoding="utf-8"
    )
    assert "--retry-all-errors" in script
    assert "HEALTH_READY=false" in script
    assert 'if [ "$HEALTH_READY" != "true" ]' in script


def test_share_intent_smoke_test_redelivers_after_launcher_anr_boundedly() -> None:
    script = (ROOT / ".github" / "scripts" / "share_intent_test.sh").read_text(
        encoding="utf-8"
    )
    assert "deliver_share_intent()" in script
    assert "SHARE_REDELIVERIES=0" in script
    assert 'if [ "$SHARE_REDELIVERIES" -lt 2 ]' in script
    assert "Re-delivering ACTION_SEND after launcher ANR" in script


def test_kill_resilience_uses_transfer_ui_and_process_death_not_force_stop() -> None:
    script = (ROOT / ".github" / "scripts" / "kill_resilience_test.sh").read_text(
        encoding="utf-8"
    )
    assert "android.intent.action.SEND" in script
    assert "find_android_ui_target.py" in script
    assert "run-as de.classydl.app kill -9" in script
    assert "pidof de.classydl.app 2>/dev/null | tr -d '\\r' || true" in script
    assert "am force-stop" not in script
    assert '-X POST "$BASE/api/queue"' not in script
