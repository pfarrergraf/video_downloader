from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / ".github/workflows/android-release.yml"
PROMOTE = ROOT / ".github/workflows/android-promote-candidate.yml"


def test_candidate_build_has_team_gate_and_never_uploads_to_play() -> None:
    source = CANDIDATE.read_text(encoding="utf-8")
    assert "name: Android candidate build" in source
    assert "fgs_declaration_confirmed" in source
    assert "team_gate_confirmed" in source
    assert "--query-highest-version-code true" in source
    assert "candidate-provenance.json" in source
    assert "play-candidate" in source
    assert "Upload App Bundle to Google Play" not in source
    assert "--expected-version-code" not in source
    assert "environment: android-candidate-signing" in source
    assert "TEAM_GATE.json" in source
    assert 'GITHUB_REF_NAME\" = \"release/v1.0.4.2-team' in source
    assert "check_android_play_aab.sh" in source
    assert "python scripts/check_no_ad_sdk.py" in source
    assert "app-direct-release.apk" not in source
    assert "check_android_release_artifacts.sh" not in source
    assert '"fgsDeclarationConfirmed": ${{ inputs.fgs_declaration_confirmed }}' in source


def test_promotion_downloads_exact_candidate_and_never_builds() -> None:
    source = PROMOTE.read_text(encoding="utf-8")
    lower = source.lower()
    assert "candidate_run_id" in source
    assert "expected_sha256" in source
    assert "run-id: ${{ inputs.candidate_run_id }}" in source
    assert "verify_android_candidate.py" in source
    assert "promotion-verifier/scripts/verify_android_candidate.py" in source
    assert "ref: ${{ github.sha }}" in source
    assert "--expected-version-code" in source
    assert "--track internal" in source
    assert "cancel-in-progress: false" in source
    assert "environment: google-play-internal" in source
    assert "fgs_declaration_confirmed" in source
    assert "must be confirmed before upload" in source
    assert 'candidate:${{ steps.candidate.outputs.aab_sha256 }}' in source
    for forbidden in ("gradle ", "bundleplayrelease", "assemblerelease", "compileplay"):
        assert forbidden not in lower


def test_promotion_is_bound_to_successful_candidate_workflow_and_board() -> None:
    source = PROMOTE.read_text(encoding="utf-8")
    assert '.name == "Android candidate build"' in source
    assert '.path == ".github/workflows/android-release.yml"' in source
    assert '.head_repository.full_name == "pfarrergraf/video_downloader"' in source
    assert '.conclusion == "success"' in source
    assert 'releaseBoardSha256' in source
    assert "ANDROID_UPLOAD_CERT_SHA256" in source
