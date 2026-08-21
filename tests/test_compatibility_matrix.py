from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_catalog_has_exact_requested_shape() -> None:
    generator = _load_script("generate_compatibility_catalog.py")
    catalog = generator.build_catalog()
    runner = _load_script("run_compatibility_matrix.py")

    runner.validate_catalog(catalog)
    assert len(catalog["sites"]) == 200
    assert len({site["domain"] for site in catalog["sites"]}) == 200
    assert catalog["counts"] == {
        "baseline": 100,
        "drm_subscription": 30,
        "adult": 25,
        "alternative": 25,
        "dach": 20,
    }


def test_public_catalog_contains_no_urls() -> None:
    catalog = json.loads((ROOT / "compatibility" / "catalog.json").read_text(encoding="utf-8"))
    serialized = json.dumps(catalog)
    assert "https://" not in serialized
    assert "http://" not in serialized


def test_failure_classification_separates_access_and_technical_errors() -> None:
    runner = _load_script("run_compatibility_matrix.py")
    assert (
        runner.classify_failure("Could not copy Chrome cookie database")
        == runner.OUTCOME_BROWSER_COOKIES
    )
    assert runner.classify_failure("This content is protected by DRM") == runner.OUTCOME_DRM
    assert runner.classify_failure("Please log in to continue") == runner.OUTCOME_LOGIN
    assert runner.classify_failure("not available in your country") == runner.OUTCOME_GEO_AGE
    assert runner.classify_failure("Your IP address is blocked from accessing this post") == runner.OUTCOME_GEO_AGE
    assert runner.classify_failure("Unsupported URL") == runner.OUTCOME_UNSUPPORTED
    assert runner.classify_failure("connection reset") == runner.OUTCOME_TECHNICAL
    assert (
        runner.classify_failure("safety byte cap exceeded (104857600 bytes)")
        == runner.OUTCOME_SIZE_LIMIT
    )


def test_domain_grades_do_not_overclaim_partial_success() -> None:
    runner = _load_script("run_compatibility_matrix.py")
    assert runner._domain_grade([runner.OUTCOME_FULL] * 3) == "3/3 confirmed"
    assert runner._domain_grade([runner.OUTCOME_FULL, runner.OUTCOME_UNSUPPORTED]) == "partial"
    assert runner._domain_grade([runner.OUTCOME_DRM] * 3) == "DRM/access protection confirmed"
    assert runner._domain_grade([runner.OUTCOME_TECHNICAL] * 3) == "0/3 not confirmed"


def test_protected_service_media_is_preview_or_safety_stop() -> None:
    runner = _load_script("run_compatibility_matrix.py")
    short_audio = [{"duration_seconds": 30, "streams": [{"codec_type": "audio"}]}]
    long_audio = [{"duration_seconds": 240, "streams": [{"codec_type": "audio"}]}]
    short_video = [{"duration_seconds": 120, "streams": [{"codec_type": "video"}]}]
    assert runner.classify_valid_media("drm_subscription", short_audio) == runner.OUTCOME_PREVIEW
    assert runner.classify_valid_media("drm_subscription", long_audio) == runner.OUTCOME_SAFETY_STOP
    assert runner.classify_valid_media("drm_subscription", short_video) == runner.OUTCOME_PREVIEW
    assert runner.classify_valid_media("baseline", long_audio) == runner.OUTCOME_FULL


def test_upstream_playlist_and_profile_fixtures_are_rejected() -> None:
    runner = _load_script("run_compatibility_matrix.py")
    assert not runner._is_single_media_fixture(
        {"url": "https://youtube.com/user/example/videos", "info_dict": {"id": "example"}}
    )
    assert not runner._is_single_media_fixture(
        {"url": "https://example.com/watch?v=1&list=abc", "info_dict": {"id": "1"}}
    )
    assert not runner._is_single_media_fixture(
        {"url": "https://example.com/video/1", "playlist_count": 3, "info_dict": {"id": "1"}}
    )
    assert runner._is_single_media_fixture(
        {"url": "https://example.com/video/1", "info_dict": {"id": "1"}}
    )


def test_attempt_byte_cap_is_bounded() -> None:
    runner = _load_script("run_compatibility_matrix.py")
    assert runner.MAX_ATTEMPT_BYTES == 100 * 1024 * 1024


def test_verification_samples_are_limited_to_unprotected_non_adult_media(
    tmp_path: Path, monkeypatch
) -> None:
    runner = _load_script("run_compatibility_matrix.py")
    media = tmp_path / "source.mp4"
    media.write_bytes(b"media")
    retained = tmp_path / "retained"

    class FakeDownloadManager:
        def __init__(self, logger):
            self.logger = logger

        def download(self, request):
            from video_downloader.models import DownloadResult

            return DownloadResult(media, "test", request.source_url, downloaded_files=[media])

    monkeypatch.setattr("video_downloader.core.DownloadManager", FakeDownloadManager)
    monkeypatch.setattr(
        runner,
        "_ffprobe",
        lambda path: {
            "valid": True,
            "duration_seconds": 5,
            "streams": [{"codec_type": "video"}],
        },
    )
    entry = {
        "domain": "example.com",
        "category": "baseline",
        "url_index": 1,
        "url": "https://example.com/video",
        "url_sha256": "hash",
    }
    result = runner._attempt(entry, timeout=1, work_dir=tmp_path, retain_dir=retained)
    assert result["access_mode"] == "anonymous"
    assert len(result["retained_files"]) == 1
    assert result["files"][0]["content_sha256"] == hashlib.sha256(b"media").hexdigest()

    adult = dict(entry, category="adult")
    result = runner._attempt(adult, timeout=1, work_dir=tmp_path, retain_dir=retained)
    assert result["retained_files"] == []


def test_authenticated_attempt_marks_access_mode_without_storing_browser_name(
    tmp_path: Path, monkeypatch
) -> None:
    runner = _load_script("run_compatibility_matrix.py")
    seen = {}

    class FailingDownloadManager:
        def __init__(self, logger):
            self.logger = logger

        def download(self, request):
            seen["browser"] = request.cookies_from_browser
            raise RuntimeError("test failure")

    monkeypatch.setattr("video_downloader.core.DownloadManager", FailingDownloadManager)
    entry = {
        "domain": "example.com",
        "category": "baseline",
        "url_index": 1,
        "url": "https://example.com/video",
        "url_sha256": "hash",
    }
    result = runner._attempt(
        entry,
        timeout=1,
        work_dir=tmp_path,
        cookies_from_browser="edge",
    )
    assert seen["browser"] == "edge"
    assert result["access_mode"] == "authenticated_browser"
    assert "edge" not in json.dumps(result)


def test_authenticated_verification_stops_before_urls_when_browser_is_running(
    monkeypatch, capsys
) -> None:
    runner = _load_script("run_compatibility_matrix.py")
    monkeypatch.setattr(runner, "_browser_process_is_running", lambda browser: True)
    result = runner.run_verification(
        domains=["youtube.com"],
        url_index=1,
        cookies_from_browser="edge",
        keep_successes=True,
        timeout=1,
        attempt_timeout=1,
    )
    assert result == 2
    assert "edge is still running" in capsys.readouterr().err


def test_authenticated_verification_stops_after_first_cookie_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    runner = _load_script("run_compatibility_matrix.py")
    manifest = {
        "entries": [
            {
                "domain": domain,
                "category": "baseline",
                "url_index": index,
                "url": f"https://{domain}/video/{index}",
                "url_sha256": f"hash-{domain}-{index}",
            }
            for domain in ("youtube.com", "tiktok.com")
            for index in (1, 2, 3)
        ]
    }
    monkeypatch.setattr(runner, "MANIFEST_PATH", tmp_path / "manifest.json")
    runner.MANIFEST_PATH.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(runner, "validate_manifest", lambda manifest, require_complete: None)
    monkeypatch.setattr(runner, "_browser_process_is_running", lambda browser: False)
    monkeypatch.setattr(runner, "VERIFICATION_DIR", tmp_path / "verification")
    monkeypatch.setattr(runner, "SAMPLE_DIR", tmp_path / "samples")
    calls = []

    def fail_cookie(entry, **kwargs):
        calls.append(entry)
        return {
            **entry,
            "outcome": runner.OUTCOME_BROWSER_COOKIES,
            "access_mode": "authenticated_browser",
            "retained_files": [],
        }

    monkeypatch.setattr(runner, "_attempt_isolated", fail_cookie)
    result = runner.run_verification(
        domains=["youtube.com", "tiktok.com"],
        url_index=None,
        cookies_from_browser="firefox",
        keep_successes=True,
        timeout=1,
        attempt_timeout=1,
    )
    assert result == 0
    assert len(calls) == 1
    assert "No remaining platform URLs were attempted" in capsys.readouterr().err
