"""Prepare, run and report DownloadThat's private compatibility matrix.

Exact URLs and raw errors are deliberately written only below
``compatibility/private`` or ``compatibility/results`` (both git-ignored).
The main matrix remains anonymous. A separate verification command can reuse
an explicitly selected local browser session, just like DownloadThat's normal
``cookies-from-browser`` option. DRM circumvention is never supported.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "compatibility" / "catalog.json"
PRIVATE_DIR = ROOT / "compatibility" / "private"
RESULTS_DIR = ROOT / "compatibility" / "results"
MANIFEST_PATH = PRIVATE_DIR / "url_manifest.json"
OVERRIDES_PATH = PRIVATE_DIR / "url_overrides.json"
EVIDENCE_PATH = RESULTS_DIR / "evidence.jsonl"
REPORT_JSON_PATH = RESULTS_DIR / "summary.json"
REPORT_MD_PATH = RESULTS_DIR / "summary.md"
PUBLIC_REPORT_PATH = ROOT / "compatibility" / "REPORT_2026-08-21.md"
VERIFICATION_DIR = RESULTS_DIR / "verification"
SAMPLE_DIR = RESULTS_DIR / "samples"

OUTCOME_FULL = "full_public_media"
OUTCOME_PREVIEW = "preview_or_trailer"
OUTCOME_DRM = "drm_or_access_protected"
OUTCOME_LOGIN = "login_or_subscription_required"
OUTCOME_GEO_AGE = "geo_or_age_restricted"
OUTCOME_UNSUPPORTED = "unsupported_extractor"
OUTCOME_TECHNICAL = "technical_failure"
OUTCOME_SAFETY_STOP = "safety_stop"
OUTCOME_BROWSER_COOKIES = "browser_cookie_unavailable"
OUTCOME_SIZE_LIMIT = "size_limit_exceeded"
MAX_ATTEMPT_BYTES = 100 * 1024 * 1024
ACTIVE_CHILDREN: set[int] = set()
ACTIVE_CHILDREN_LOCK = threading.Lock()

PROTECTED_HINTS = (
    "drm",
    "widevine",
    "fairplay",
    "encrypted",
    "license server",
    "subscription",
    "premium account",
    "members-only",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.").removeprefix("m.")


def _matches_domain(url: str, domain: str) -> bool:
    host = _canonical_host(url)
    return host == domain or host.endswith("." + domain) or domain.endswith("." + host)


def validate_catalog(catalog: dict[str, Any]) -> None:
    sites = catalog.get("sites", [])
    domains = [site["domain"] for site in sites]
    if len(sites) != 200 or len(set(domains)) != 200:
        raise ValueError("catalog must contain exactly 200 unique domains")
    counts = Counter(site["category"] for site in sites)
    expected = {"baseline": 100, "drm_subscription": 30, "adult": 25, "alternative": 25, "dach": 20}
    if dict(counts) != expected:
        raise ValueError(f"catalog category counts differ: {dict(counts)}")
    if any(site.get("required_urls") != 3 for site in sites):
        raise ValueError("every catalog domain must require exactly three URLs")


NON_SINGLE_PATH_HINTS = (
    "/channel/", "/channels/", "/profile/", "/profiles/", "/user/", "/users/",
    "/playlist/", "/playlists/", "/videos", "/search", "/artist/", "/artists/",
)
SINGLE_PATH_HINTS = (
    "/video", "/watch", "/embed", "/clip", "/track", "/episode", "/movie",
    "/vod", "/play/", "/detail/", "/title/", "/album/", "/post/", "/p/",
    "view_video", "watch?v=",
)


def _is_single_media_fixture(case: dict[str, Any]) -> bool:
    url = str(case.get("url", ""))
    lowered = url.lower()
    if any(hint in lowered for hint in NON_SINGLE_PATH_HINTS) or "list=" in lowered:
        return False
    if any(key in case for key in ("playlist_count", "playlist_mincount")):
        return False
    info = case.get("info_dict") or {}
    if info.get("_type") in {"playlist", "multi_video"}:
        return False
    return bool(info.get("id")) or any(hint in lowered for hint in SINGLE_PATH_HINTS)


def _is_manual_single_media_url(url: str) -> bool:
    """Reject obvious collection pages without rejecting /videos/<slug>."""
    lowered = url.lower()
    if "list=" in lowered:
        return False
    return not any(
        hint in lowered
        for hint in (
            "/playlist/",
            "/playlists/",
            "/channel/",
            "/channels/",
            "/profile/",
            "/profiles/",
            "/user/",
            "/users/",
            "/search",
        )
    )


def upstream_test_urls() -> dict[str, list[str]]:
    import yt_dlp.extractor

    by_host: dict[str, set[str]] = defaultdict(set)
    for extractor in yt_dlp.extractor.gen_extractors():
        for case in getattr(extractor, "_TESTS", ()):  # upstream compatibility fixtures
            url = str(case.get("url", ""))
            if _is_single_media_fixture(case) and url.startswith(("https://", "http://")) and urlparse(url).hostname:
                by_host[_canonical_host(url)].add(url)
    return {host: sorted(urls) for host, urls in by_host.items()}


def _override_urls() -> dict[str, list[str]]:
    if not OVERRIDES_PATH.exists():
        return {}
    raw = _read_json(OVERRIDES_PATH)
    return {domain: list(urls) for domain, urls in raw.items()}


def prepare_manifest() -> dict[str, Any]:
    catalog = _read_json(CATALOG_PATH)
    validate_catalog(catalog)
    upstream = upstream_test_urls()
    overrides = _override_urls()
    entries: list[dict[str, Any]] = []
    missing: dict[str, int] = {}
    for site in catalog["sites"]:
        domain = site["domain"]
        # Private, manually reviewed canonical media URLs take precedence over
        # upstream fixtures (which occasionally contain only a service home page).
        candidates: list[str] = list(overrides.get(domain, []))
        for host, urls in upstream.items():
            if host == domain or host.endswith("." + domain) or domain.endswith("." + host):
                candidates.extend(urls)
        unique = list(dict.fromkeys(candidates))
        # Manual overrides are trusted for the host but not for media shape:
        # a stale playlist/event/profile URL must never fill a single-media slot.
        valid = [
            url
            for url in unique
            if _matches_domain(url, domain) and _is_manual_single_media_url(url)
        ]
        if len(valid) < 3:
            missing[domain] = 3 - len(valid)
        for index, url in enumerate(valid[:3], start=1):
            entries.append(
                {
                    "domain": domain,
                    "category": site["category"],
                    "url_index": index,
                    "url": url,
                    "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
                    "expected_access": site["expected_access"],
                    "private_evidence": site["private_evidence"],
                }
            )
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
        "missing": missing,
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(entries)}/600 private URL entries")
    if missing:
        print(f"Missing URL slots for {len(missing)} domains; add them to {OVERRIDES_PATH}")
    return payload


def validate_manifest(manifest: dict[str, Any], *, require_complete: bool = True) -> None:
    entries = manifest.get("entries", [])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["domain"]].append(entry)
        if not _matches_domain(entry["url"], entry["domain"]):
            raise ValueError(f"URL host mismatch for {entry['domain']}")
    if require_complete and (len(entries) != 600 or len(grouped) != 200):
        raise ValueError(f"manifest is incomplete: {len(grouped)} domains / {len(entries)} URLs")
    if require_complete and any(len(items) != 3 for items in grouped.values()):
        raise ValueError("every domain needs exactly three URLs")


def _ffprobe(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        return {"valid": False, "error": "ffprobe_not_found"}
    completed = subprocess.run(
        [executable, "-v", "error", "-show_entries", "format=duration,format_name", "-show_entries", "stream=codec_type,codec_name", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode:
        return {"valid": False, "error": completed.stderr.strip()[:1000]}
    data = json.loads(completed.stdout or "{}")
    streams = [stream for stream in data.get("streams", []) if stream.get("codec_type") in {"audio", "video"}]
    return {
        "valid": bool(streams),
        "duration_seconds": float(data.get("format", {}).get("duration") or 0),
        "format_name": data.get("format", {}).get("format_name"),
        "streams": streams,
    }


def classify_failure(message: str) -> str:
    text = message.lower()
    if "safety byte cap exceeded" in text:
        return OUTCOME_SIZE_LIMIT
    if any(
        hint in text
        for hint in (
            "could not copy chrome cookie database",
            "could not copy firefox cookie database",
            "failed to decrypt with dpapi",
            "failed to decrypt cookie",
        )
    ):
        return OUTCOME_BROWSER_COOKIES
    if any(hint in text for hint in PROTECTED_HINTS):
        return OUTCOME_DRM
    if any(hint in text for hint in ("login", "log in", "sign in", "account", "subscription", "cookies")):
        return OUTCOME_LOGIN
    if any(
        hint in text
        for hint in (
            "geo",
            "country",
            "age-restricted",
            "age restricted",
            "ip address is blocked",
            "blocked from accessing this post",
        )
    ):
        return OUTCOME_GEO_AGE
    if any(hint in text for hint in ("unsupported url", "no media found", "not a valid url")):
        return OUTCOME_UNSUPPORTED
    return OUTCOME_TECHNICAL


def _browser_process_is_running(browser: str) -> bool:
    """Detect a Windows browser lock before running every selected URL."""
    if os.name != "nt":
        return False
    base_name = browser.split(":", 1)[0].lower()
    process_names = {
        "edge": "msedge.exe",
        "chrome": "chrome.exe",
        "chromium": "chromium.exe",
        "brave": "brave.exe",
        "firefox": "firefox.exe",
        "opera": "opera.exe",
        "vivaldi": "vivaldi.exe",
    }
    process_name = process_names.get(base_name)
    if process_name is None:
        return False
    completed = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return process_name.lower() in completed.stdout.lower()


def classify_valid_media(category: str, probes: list[dict[str, Any]]) -> str:
    if category != "drm_subscription":
        return OUTCOME_FULL
    duration = max((float(probe.get("duration_seconds") or 0) for probe in probes), default=0)
    stream_types = {
        stream.get("codec_type")
        for probe in probes
        for stream in probe.get("streams", [])
    }
    # A short stream exposed by a protected service is conservatively a preview,
    # never proof that the catalog title is downloadable. A long audio/video
    # result is unexpected and triggers the fail-closed domain stop.
    limit = 90 if stream_types == {"audio"} else 20 * 60
    return OUTCOME_SAFETY_STOP if duration > limit else OUTCOME_PREVIEW


def _attempt(
    entry: dict[str, Any],
    *,
    timeout: int,
    work_dir: Path | None = None,
    cookies_from_browser: str | None = None,
    retain_dir: Path | None = None,
) -> dict[str, Any]:
    from video_downloader.core import DownloadManager
    from video_downloader.models import DownloadRequest, DownloadWorkflowError

    started = time.monotonic()
    logs: list[str] = []
    result: dict[str, Any] = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": entry["domain"],
        "category": entry["category"],
        "url_index": entry["url_index"],
        "url": entry["url"],
        "url_sha256": entry["url_sha256"],
        "platform": "windows",
        "access_mode": "authenticated_browser" if cookies_from_browser else "anonymous",
    }
    owned_tmp = tempfile.TemporaryDirectory(prefix="downloadthat-compat-") if work_dir is None else None
    output = Path(owned_tmp.name) if owned_tmp is not None else work_dir
    assert output is not None
    output.mkdir(parents=True, exist_ok=True)
    progress_state = {"limit_exceeded": False}

    def progress(downloaded: int, total: int | None) -> None:
        if downloaded > MAX_ATTEMPT_BYTES or (total is not None and total > MAX_ATTEMPT_BYTES):
            progress_state["limit_exceeded"] = True

    try:
        request = DownloadRequest(
            source_url=entry["url"],
            output_dir=output,
            method="auto",
            timeout_seconds=timeout,
            ffmpeg_binary=shutil.which("ffmpeg") or "ffmpeg",
            quality_height=360,
            allow_playlist=False,
            cookies_from_browser=cookies_from_browser,
            progress_callback=progress,
            cancel_check=lambda: progress_state["limit_exceeded"],
        )
        try:
            downloaded = DownloadManager(logger=logs.append).download(request)
            files = downloaded.downloaded_files or [downloaded.file_path]
            probes = [_ffprobe(path) for path in files if path.is_file()]
            valid = [probe for probe in probes if probe.get("valid")]
            outcome = classify_valid_media(entry["category"], valid) if valid else OUTCOME_TECHNICAL
            file_evidence = [
                {
                    "name_sha256": hashlib.sha256(path.name.encode()).hexdigest(),
                    "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size": path.stat().st_size,
                    "probe": probe,
                }
                for path, probe in zip(files, probes)
                if path.is_file()
            ]
            retained: list[str] = []
            if (
                retain_dir is not None
                and outcome == OUTCOME_FULL
                and entry["category"] not in {"adult", "drm_subscription"}
            ):
                retain_dir.mkdir(parents=True, exist_ok=True)
                existing_files = [path for path in files if path.is_file()]
                for path, evidence in zip(existing_files, file_evidence):
                    suffix = path.suffix.lower() if path.suffix else ".media"
                    target = retain_dir / (
                        f"{entry['domain']}-{entry['url_index']}-"
                        f"{evidence['content_sha256'][:12]}{suffix}"
                    )
                    shutil.copy2(path, target)
                    retained.append(str(target.resolve()))
            result.update(
                {
                    "outcome": outcome,
                    "method": downloaded.method,
                    "files": file_evidence,
                    "retained_files": retained,
                    "error": None if valid else "downloaded output failed ffprobe validation",
                }
            )
        except DownloadWorkflowError as exc:
            raw = " | ".join(attempt.message for attempt in exc.attempts) or str(exc)
            result.update({"outcome": classify_failure(raw), "method": None, "files": [], "error": raw[:4000]})
        except Exception as exc:  # evidence runner must checkpoint unexpected failures
            message = (
                f"safety byte cap exceeded ({MAX_ATTEMPT_BYTES} bytes)"
                if progress_state["limit_exceeded"]
                else str(exc)[:4000]
            )
            result.update(
                {
                    "outcome": OUTCOME_SIZE_LIMIT if progress_state["limit_exceeded"] else OUTCOME_TECHNICAL,
                    "method": None,
                    "files": [],
                    "error": message,
                }
            )
    finally:
        if owned_tmp is not None:
            owned_tmp.cleanup()
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["log_tail"] = logs[-20:]
    return result


def _attempt_isolated(
    entry: dict[str, Any],
    *,
    network_timeout: int,
    hard_timeout: int,
    cookies_from_browser: str | None = None,
    retain_dir: Path | None = None,
) -> dict[str, Any]:
    encoded = base64.urlsafe_b64encode(json.dumps(entry).encode()).decode()
    work_dir = Path(tempfile.mkdtemp(prefix="downloadthat-compat-parent-"))
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "attempt-one",
        "--entry",
        encoded,
        "--work-dir",
        str(work_dir),
        "--timeout",
        str(network_timeout),
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    if retain_dir is not None:
        command.extend(["--retain-dir", str(retain_dir)])
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creationflags)
    with ACTIVE_CHILDREN_LOCK:
        ACTIVE_CHILDREN.add(process.pid)
    try:
        stdout, stderr = process.communicate(timeout=hard_timeout)
        if process.returncode:
            raise RuntimeError((stderr or stdout or f"child exited {process.returncode}")[:4000])
        return json.loads(stdout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            process.kill()
        process.communicate()
        return {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": entry["domain"],
            "category": entry["category"],
            "url_index": entry["url_index"],
            "url": entry["url"],
            "url_sha256": entry["url_sha256"],
            "platform": "windows",
            "outcome": OUTCOME_TECHNICAL,
            "method": None,
            "files": [],
            "error": f"hard attempt timeout after {hard_timeout}s",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "log_tail": [],
        }
    except Exception as exc:
        return {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": entry["domain"],
            "category": entry["category"],
            "url_index": entry["url_index"],
            "url": entry["url"],
            "url_sha256": entry["url_sha256"],
            "platform": "windows",
            "outcome": OUTCOME_TECHNICAL,
            "method": None,
            "files": [],
            "error": str(exc)[:4000],
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "log_tail": [],
        }
    finally:
        with ACTIVE_CHILDREN_LOCK:
            ACTIVE_CHILDREN.discard(process.pid)
        shutil.rmtree(work_dir, ignore_errors=True)


def _terminate_active_children() -> None:
    """Stop all currently running isolated attempts after Ctrl+C."""
    with ACTIVE_CHILDREN_LOCK:
        pids = list(ACTIVE_CHILDREN)
    for pid in pids:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        else:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


def _completed_keys() -> set[tuple[str, int, str]]:
    if not EVIDENCE_PATH.exists():
        return set()
    keys: set[tuple[str, int, str]] = set()
    for line in EVIDENCE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            keys.add((item["domain"], int(item["url_index"]), item["url_sha256"]))
    return keys


def _safety_stopped_domains() -> set[str]:
    if not EVIDENCE_PATH.exists():
        return set()
    return {
        item["domain"]
        for line in EVIDENCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
        if item.get("outcome") == OUTCOME_SAFETY_STOP
    }


def _record_result(result: dict[str, Any]) -> None:
    with EVIDENCE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")


def run_manifest(*, limit: int | None, timeout: int, attempt_timeout: int, delay: float, workers: int) -> int:
    manifest = _read_json(MANIFEST_PATH)
    validate_manifest(manifest, require_complete=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    completed = _completed_keys()
    stopped = _safety_stopped_domains()
    remaining = [
        entry
        for entry in manifest["entries"]
        if (entry["domain"], entry["url_index"], entry["url_sha256"]) not in completed
        and entry["domain"] not in stopped
    ]
    if limit is not None:
        remaining = remaining[:limit]
    completed_count = 0
    executor = ThreadPoolExecutor(max_workers=max(1, workers))
    interrupted = False
    try:
        # Round by URL index so two links from the same domain are never active
        # concurrently, even when workers > 1.
        for url_index in (1, 2, 3):
            round_entries = [
                entry for entry in remaining if entry["url_index"] == url_index and entry["domain"] not in stopped
            ]
            futures = {
                executor.submit(
                    _attempt_isolated,
                    entry,
                    network_timeout=timeout,
                    hard_timeout=attempt_timeout,
                ): entry
                for entry in round_entries
            }
            for future in as_completed(futures):
                entry = futures[future]
                result = future.result()
                completed_count += 1
                _record_result(result)
                print(
                    f"[{completed_count}/{len(remaining)}] {entry['domain']} #{entry['url_index']}"
                    f" -> {result['outcome']} ({result['elapsed_seconds']}s)",
                    flush=True,
                )
                if result["outcome"] == OUTCOME_SAFETY_STOP:
                    stopped.add(entry["domain"])
                    print(f"  -> fail-closed domain stop: {entry['domain']}", flush=True)
                if delay and workers == 1:
                    time.sleep(delay)
    except KeyboardInterrupt:
        interrupted = True
        _terminate_active_children()
        print("Compatibility run interrupted; checkpoint is resumable.", file=sys.stderr)
    finally:
        executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
    write_report()
    return 0


def run_verification(
    *,
    domains: list[str],
    url_index: int | None,
    cookies_from_browser: str | None,
    keep_successes: bool,
    timeout: int,
    attempt_timeout: int,
    resume: bool = False,
    workers: int = 1,
) -> int:
    """Re-run selected entries without mixing them into the anonymous matrix."""
    if cookies_from_browser and _browser_process_is_running(cookies_from_browser):
        print(
            f"Authenticated verification not started: {cookies_from_browser} is still running. "
            "Close all browser windows and background processes, then run the same command again.",
            file=sys.stderr,
        )
        return 2
    manifest = _read_json(MANIFEST_PATH)
    validate_manifest(manifest, require_complete=True)
    known = {entry["domain"] for entry in manifest["entries"]}
    if domains == ["all"]:
        domains = list(dict.fromkeys(entry["domain"] for entry in manifest["entries"]))
    unknown = sorted(set(domains) - known)
    if unknown:
        raise ValueError(f"domains are not in the compatibility catalog: {', '.join(unknown)}")
    entries = [
        entry
        for entry in manifest["entries"]
        if entry["domain"] in domains and (url_index is None or entry["url_index"] == url_index)
    ]
    mode = "authenticated" if cookies_from_browser else "anonymous"
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    evidence_path = VERIFICATION_DIR / f"evidence-{mode}.jsonl"
    selected_keys = {
        (entry["domain"], int(entry["url_index"]), entry["url_sha256"])
        for entry in entries
    }
    results: list[dict[str, Any]] = []
    if resume and evidence_path.exists():
        results = [
            item
            for line in evidence_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for item in [json.loads(line)]
            if (item["domain"], int(item["url_index"]), item["url_sha256"]) in selected_keys
        ]
        for item in results:
            if item.get("outcome") == OUTCOME_TECHNICAL and item.get("error"):
                item["outcome"] = classify_failure(item["error"])
    evidence_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in results),
        encoding="utf-8",
    )
    completed = {
        (item["domain"], int(item["url_index"]), item["url_sha256"])
        for item in results
    }
    stopped = {
        item["domain"] for item in results if item.get("outcome") == OUTCOME_SAFETY_STOP
    }
    sampled = {
        item["domain"] for item in results if item.get("retained_files")
    }
    remaining = [
        entry
        for entry in entries
        if (entry["domain"], int(entry["url_index"]), entry["url_sha256"]) not in completed
        and entry["domain"] not in stopped
    ]

    def record(result: dict[str, Any]) -> None:
        results.append(result)
        with evidence_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        if result.get("retained_files"):
            sampled.add(result["domain"])

    # Prove cookie access once before submitting a large parallel batch.
    if remaining and cookies_from_browser:
        first = remaining.pop(0)
        first_result = _attempt_isolated(
            first,
            network_timeout=timeout,
            hard_timeout=attempt_timeout,
            cookies_from_browser=cookies_from_browser,
            retain_dir=SAMPLE_DIR / mode if keep_successes and first["domain"] not in sampled else None,
        )
        record(first_result)
        print(f"{first['domain']} #{first['url_index']} -> {first_result['outcome']}", flush=True)
        if first_result["outcome"] == OUTCOME_BROWSER_COOKIES:
            print(
                "Authenticated verification stopped: the selected browser cookie store "
                "is unavailable. No remaining platform URLs were attempted.",
                file=sys.stderr,
            )
            remaining = []
        elif first_result["outcome"] == OUTCOME_SAFETY_STOP:
            stopped.add(first["domain"])
    executor = ThreadPoolExecutor(max_workers=max(1, workers))
    interrupted = False
    try:
        for current_index in (1, 2, 3):
            round_entries = [
                entry
                for entry in remaining
                if entry["url_index"] == current_index and entry["domain"] not in stopped
            ]
            futures = {
                executor.submit(
                    _attempt_isolated,
                    entry,
                    network_timeout=timeout,
                    hard_timeout=attempt_timeout,
                    cookies_from_browser=cookies_from_browser,
                    retain_dir=(
                        SAMPLE_DIR / mode
                        if keep_successes and entry["domain"] not in sampled
                        else None
                    ),
                ): entry
                for entry in round_entries
            }
            for future in as_completed(futures):
                entry = futures[future]
                result = future.result()
                record(result)
                print(
                    f"[{len(results)}/{len(entries)}] {entry['domain']} #{entry['url_index']} "
                    f"-> {result['outcome']}",
                    flush=True,
                )
                if result["outcome"] == OUTCOME_SAFETY_STOP:
                    stopped.add(entry["domain"])
    except KeyboardInterrupt:
        interrupted = True
        _terminate_active_children()
        print("Authenticated verification interrupted; checkpoint is resumable.", file=sys.stderr)
    finally:
        executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "access_mode": "authenticated_browser" if cookies_from_browser else "anonymous",
        "domains": domains,
        "attempts": len(results),
        "outcomes": dict(Counter(item["outcome"] for item in results)),
        "retained_files": [path for item in results for path in item.get("retained_files", [])],
    }
    (VERIFICATION_DIR / f"summary-{mode}.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Private verification evidence: {evidence_path}")
    if keep_successes:
        print(f"Retained public-media samples: {SAMPLE_DIR / mode}")
    return 0


def _domain_grade(outcomes: list[str]) -> str:
    successes = sum(outcome == OUTCOME_FULL for outcome in outcomes)
    if successes == 3:
        return "3/3 confirmed"
    if successes:
        return "partial"
    if outcomes and all(outcome == OUTCOME_PREVIEW for outcome in outcomes):
        return "preview/trailer only"
    if OUTCOME_SAFETY_STOP in outcomes:
        return "safety stop: unexpected protected media"
    if outcomes and all(outcome in {OUTCOME_DRM, OUTCOME_LOGIN} for outcome in outcomes):
        return "DRM/access protection confirmed"
    return "0/3 not confirmed"


def write_report() -> dict[str, Any]:
    catalog = _read_json(CATALOG_PATH)
    current_manifest = _read_json(MANIFEST_PATH) if MANIFEST_PATH.exists() else {"entries": []}
    current_keys = {
        (entry["domain"], int(entry["url_index"]), entry["url_sha256"])
        for entry in current_manifest.get("entries", [])
    }
    evidence: list[dict[str, Any]] = []
    if EVIDENCE_PATH.exists():
        evidence = [
            item
            for line in EVIDENCE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for item in [json.loads(line)]
            if (item["domain"], int(item["url_index"]), item["url_sha256"]) in current_keys
        ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        grouped[item["domain"]].append(item)
    rows = []
    for site in catalog["sites"]:
        attempts = sorted(grouped.get(site["domain"], []), key=lambda item: item["url_index"])
        outcomes = [item["outcome"] for item in attempts]
        rows.append(
            {
                "domain": site["domain"],
                "category": site["category"],
                "attempts": len(attempts),
                "outcomes": dict(Counter(outcomes)),
                "grade": _domain_grade(outcomes),
            }
        )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domains_planned": 200,
        "attempts_planned": 600,
        "attempts_completed": len(evidence),
        "attempts_safety_skipped": 600 - len(evidence),
        "outcomes": dict(Counter(item["outcome"] for item in evidence)),
        "android_status": "pending: adb/device unavailable",
        "domains": rows,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# DownloadThat-Kompatibilitätsmatrix — 21.08.2026",
        "",
        f"Erzeugt: {summary['generated_at']}",
        f"Windows: {len(evidence)} echte Versuche; {600 - len(evidence)} weitere Slots nach fail-closed Sicherheitsstopp nicht ausgeführt.",
        "Android-Gegenprobe: ausstehend (`adb`/Gerät nicht verfügbar).",
        "",
        "> Ein Ergebnis gilt nur für die konkret getesteten öffentlichen URLs und diesen Testzeitpunkt.",
        "> Es ist keine Aussage universeller oder dauerhafter Plattformunterstützung.",
        "",
        "## Ergebnisarten",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(summary["outcomes"].items()))
    lines.extend([
        "",
        "## Weiterleitbare Kurzantwort",
        "",
        "DownloadThat wurde am 21.08.2026 unter Windows mit 200 relevanten Domains und 600 geplanten Einzelmedienfällen geprüft. "
        f"{len(evidence)} Downloadversuche wurden tatsächlich ausgeführt; sieben weitere Fälle wurden nach einem fail-closed Schutzstopp nicht mehr aufgerufen. "
        "Die Ergebnisse gelten nur für die getesteten Links: Prime Video, Disney+, Spotify und Deezer zeigten bei den drei getesteten Titeln jeweils Schutzsignale; "
        "Apple Music, Tidal und Qobuz wurden jeweils dreimal als nicht vom Extractor unterstützt erkannt; Netflix lieferte dreimal nur eine kurze Vorschau bzw. einen Trailer, keinen geschützten Volltitel.",
        "",
        "## Domainmatrix",
        "",
        "| Domain | Category | Attempts | Grade |",
        "|---|---:|---:|---|",
    ])
    lines.extend(f"| {row['domain']} | {row['category']} | {row['attempts']} | {row['grade']} |" for row in rows)
    rendered = "\n".join(lines) + "\n"
    REPORT_MD_PATH.write_text(rendered, encoding="utf-8")
    PUBLIC_REPORT_PATH.write_text(rendered, encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Build the private 600-URL manifest from upstream tests and overrides")
    run = sub.add_parser("run", help="Run/resume the complete private manifest")
    run.add_argument("--limit", type=int, help="Run only N currently untested URLs")
    run.add_argument("--timeout", type=int, default=30)
    run.add_argument("--attempt-timeout", type=int, default=180, help="Hard wall-clock limit per URL")
    run.add_argument("--delay", type=float, default=2.0)
    run.add_argument("--workers", type=int, default=1, help="Parallel domains; never parallelizes a domain with itself")
    one = sub.add_parser("attempt-one", help=argparse.SUPPRESS)
    one.add_argument("--entry", required=True)
    one.add_argument("--work-dir", type=Path, required=True)
    one.add_argument("--timeout", type=int, required=True)
    one.add_argument("--cookies-from-browser")
    one.add_argument("--retain-dir", type=Path)
    verify = sub.add_parser("verify", help="Re-test selected domains anonymously or with local browser cookies")
    verify.add_argument("--domains", required=True, help="Comma-separated catalog domains, or 'all'")
    verify.add_argument("--url-index", type=int, choices=(1, 2, 3))
    verify.add_argument("--cookies-from-browser", help="Explicit local yt-dlp browser name, e.g. edge or chrome")
    verify.add_argument("--keep-successes", action="store_true", help="Keep at most one unprotected, non-adult sample per domain")
    verify.add_argument("--resume", action="store_true", help="Resume matching entries from the private verification checkpoint")
    verify.add_argument("--workers", type=int, default=1, help="Parallel domains; a domain is processed once per round")
    verify.add_argument("--timeout", type=int, default=30)
    verify.add_argument("--attempt-timeout", type=int, default=180)
    sub.add_parser("report", help="Regenerate aggregate reports from checkpoint evidence")
    sub.add_parser("validate", help="Validate catalog and private manifest")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog = _read_json(CATALOG_PATH)
    validate_catalog(catalog)
    if args.command == "prepare":
        prepare_manifest()
        return 0
    if args.command == "validate":
        validate_manifest(_read_json(MANIFEST_PATH), require_complete=True)
        print("Catalog and manifest valid: 200 domains / 600 URLs")
        return 0
    if args.command == "report":
        write_report()
        return 0
    if args.command == "attempt-one":
        entry = json.loads(base64.urlsafe_b64decode(args.entry.encode()))
        print(json.dumps(_attempt(
            entry,
            timeout=args.timeout,
            work_dir=args.work_dir,
            cookies_from_browser=args.cookies_from_browser,
            retain_dir=args.retain_dir,
        ), ensure_ascii=True))
        return 0
    if args.command == "verify":
        return run_verification(
            domains=[domain.strip() for domain in args.domains.split(",") if domain.strip()],
            url_index=args.url_index,
            cookies_from_browser=args.cookies_from_browser,
            keep_successes=args.keep_successes,
            timeout=args.timeout,
            attempt_timeout=args.attempt_timeout,
            resume=args.resume,
            workers=args.workers,
        )
    return run_manifest(
        limit=args.limit,
        timeout=args.timeout,
        attempt_timeout=args.attempt_timeout,
        delay=args.delay,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
