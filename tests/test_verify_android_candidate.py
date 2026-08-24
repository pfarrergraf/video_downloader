import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_android_candidate import verify_candidate


def _candidate(tmp_path: Path, *, content: bytes = b"candidate") -> tuple[Path, str]:
    digest = hashlib.sha256(content).hexdigest()
    (tmp_path / "DownloadThat-v1.0.4.2-play.aab").write_bytes(content)
    (tmp_path / "candidate-provenance.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "packageName": "de.classydl.app",
                "releaseTag": "v1.0.4.2",
                "versionName": "1.0.4.2",
                "versionCode": 1000402,
                "commitSha": "a" * 40,
                "workflowRunId": "123",
                "artifactName": "DownloadThat-v1.0.4.2-play-candidate",
                "aabFile": "DownloadThat-v1.0.4.2-play.aab",
                "aabSha256": digest,
                "uploadCertificateSha256": "B" * 64,
                "releaseBoardSha256": "c" * 64,
                "fgsDeclarationConfirmed": True,
                "teamGateConfirmed": True,
            }
        ),
        encoding="utf-8",
    )
    return tmp_path, digest


def test_verify_candidate_accepts_exact_artifact(tmp_path: Path) -> None:
    directory, digest = _candidate(tmp_path)
    result = verify_candidate(
        directory,
        expected_run_id="123",
        expected_sha256=digest.upper(),
        expected_artifact_name="DownloadThat-v1.0.4.2-play-candidate",
    )
    assert result["aabSha256"] == digest
    assert result["versionCode"] == 1000402


@pytest.mark.parametrize("field", ["workflowRunId", "artifactName", "packageName"])
def test_verify_candidate_rejects_identity_mismatch(tmp_path: Path, field: str) -> None:
    directory, digest = _candidate(tmp_path)
    manifest_path = directory / "candidate-provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = "wrong"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_candidate(
            directory,
            expected_run_id="123",
            expected_sha256=digest,
            expected_artifact_name="DownloadThat-v1.0.4.2-play-candidate",
        )


def test_verify_candidate_rejects_changed_aab(tmp_path: Path) -> None:
    directory, digest = _candidate(tmp_path)
    (directory / "DownloadThat-v1.0.4.2-play.aab").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_candidate(
            directory,
            expected_run_id="123",
            expected_sha256=digest,
            expected_artifact_name="DownloadThat-v1.0.4.2-play-candidate",
        )
