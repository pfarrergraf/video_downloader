"""Verify an immutable Android candidate package before Play promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT = re.compile(r"^[0-9a-fA-F]{40,64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_candidate(
    candidate_dir: Path,
    *,
    expected_run_id: str,
    expected_sha256: str,
    expected_artifact_name: str,
    expected_package: str = "de.classydl.app",
) -> dict[str, str | int | bool]:
    manifest_path = candidate_dir / "candidate-provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schemaVersion",
        "packageName",
        "releaseTag",
        "versionName",
        "versionCode",
        "commitSha",
        "workflowRunId",
        "artifactName",
        "aabFile",
        "aabSha256",
        "uploadCertificateSha256",
        "releaseBoardSha256",
        "teamGateSha256",
        "fgsDeclarationConfirmed",
        "teamGateConfirmed",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValueError(f"candidate provenance is missing: {', '.join(missing)}")
    if manifest["schemaVersion"] != 1:
        raise ValueError("unsupported candidate provenance schema")
    if str(manifest["workflowRunId"]) != str(expected_run_id):
        raise ValueError("candidate run id does not match promotion input")
    if manifest["artifactName"] != expected_artifact_name:
        raise ValueError("candidate artifact name does not match promotion input")
    if manifest["packageName"] != expected_package:
        raise ValueError("candidate package name is not DownloadThat")
    if not manifest["fgsDeclarationConfirmed"] or not manifest["teamGateConfirmed"]:
        raise ValueError("candidate was built without all release gates")
    if not COMMIT.fullmatch(str(manifest["commitSha"])):
        raise ValueError("candidate commit SHA is invalid")
    if not HEX_64.fullmatch(str(manifest["uploadCertificateSha256"])):
        raise ValueError("candidate upload certificate digest is invalid")
    if not HEX_64.fullmatch(str(manifest["releaseBoardSha256"])):
        raise ValueError("candidate release-board digest is invalid")
    if not HEX_64.fullmatch(str(manifest["teamGateSha256"])):
        raise ValueError("candidate TEAM-gate digest is invalid")
    expected = expected_sha256.lower()
    if not HEX_64.fullmatch(expected):
        raise ValueError("expected candidate SHA-256 is invalid")
    aab_name = str(manifest["aabFile"])
    if Path(aab_name).name != aab_name or not aab_name.endswith(".aab"):
        raise ValueError("candidate AAB filename is unsafe")
    aab_path = candidate_dir / aab_name
    actual = _sha256(aab_path)
    if str(manifest["aabSha256"]).lower() != actual or expected != actual:
        raise ValueError("candidate AAB SHA-256 mismatch")
    version_code = manifest["versionCode"]
    if not isinstance(version_code, int) or version_code <= 0:
        raise ValueError("candidate versionCode is invalid")
    return {**manifest, "aabPath": str(aab_path), "aabSha256": actual}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-artifact-name", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    result = verify_candidate(
        args.candidate_dir,
        expected_run_id=args.expected_run_id,
        expected_sha256=args.expected_sha256,
        expected_artifact_name=args.expected_artifact_name,
    )
    outputs = {
        "aab_path": result["aabPath"],
        "aab_sha256": result["aabSha256"],
        "artifact_name": result["artifactName"],
        "commit_sha": result["commitSha"],
        "release_tag": result["releaseTag"],
        "version_name": result["versionName"],
        "version_code": result["versionCode"],
        "upload_cert_sha256": result["uploadCertificateSha256"],
        "release_board_sha256": result["releaseBoardSha256"],
        "team_gate_sha256": result["teamGateSha256"],
    }
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    print(json.dumps(outputs, sort_keys=True))


if __name__ == "__main__":
    main()
