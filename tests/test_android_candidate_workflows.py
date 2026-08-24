from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / ".github/workflows/android-release.yml"
PROMOTE = ROOT / ".github/workflows/android-promote-candidate.yml"


def test_candidate_build_has_hard_gates_and_never_uploads_to_play() -> None:
    source = CANDIDATE.read_text(encoding="utf-8")
    assert "name: Android candidate build" in source
    assert "fgs_declaration_confirmed" in source
    assert "team_gate_confirmed" in source
    assert "--query-highest-version-code true" in source
    assert "candidate-provenance.json" in source
    assert "play-candidate" in source
    assert "Upload App Bundle to Google Play" not in source
    assert "--expected-version-code" not in source


def test_promotion_downloads_exact_candidate_and_never_builds() -> None:
    source = PROMOTE.read_text(encoding="utf-8")
    lower = source.lower()
    assert "candidate_run_id" in source
    assert "expected_sha256" in source
    assert "run-id: ${{ inputs.candidate_run_id }}" in source
    assert "verify_android_candidate.py" in source
    assert "--expected-version-code" in source
    assert "--track internal" in source
    assert "cancel-in-progress: false" in source
    for forbidden in ("gradle ", "bundleplayrelease", "assemblerelease", "compileplay"):
        assert forbidden not in lower


def test_promotion_is_bound_to_successful_candidate_workflow_and_board() -> None:
    source = PROMOTE.read_text(encoding="utf-8")
    assert '.name == "Android candidate build"' in source
    assert '.conclusion == "success"' in source
    assert 'releaseBoardSha256' in source
    assert "ANDROID_UPLOAD_CERT_SHA256" in source
