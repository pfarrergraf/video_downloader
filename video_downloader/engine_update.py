"""Runtime self-update for the yt-dlp download engine (stdlib only).

Why this exists: yt-dlp breaks whenever YouTube/Instagram/... change their
sites, and the fix is always "get the newest yt-dlp". The version bundled
into the APK is frozen at build time, so without this module every site
change means shipping (and every user installing) a whole new APK — the
exact failure mode NewPipe users suffer through. With it, the app fetches
the latest yt-dlp wheel from PyPI, verifies it, and swaps it in at runtime;
Seal/YTDLnis do the same via GitHub releases.

Security posture (owner-approved 2026-07-07):
- Only ever talks to https://pypi.org for the hardcoded project name.
- The wheel's SHA-256 must match the digest PyPI reports (same trust anchor
  as pip itself: TLS to pypi.org).
- No downgrades: a candidate older than the bundled or currently-active
  version is rejected, so a stale/poisoned index can't roll the engine back.
- Zip entries are validated against path traversal before extraction.
- Any validation failure falls back silently to the bundled engine — the
  app can never end up without a working yt-dlp.

Layout under <data_dir>/engine/:
    yt_dlp-<version>/yt_dlp/...   extracted wheel contents (a plain dir on
                                  sys.path — Chaquopy-safe, no zipimport)
    current.json                  {"version": ..., "path": ...} (atomic)
    state.json                    {"last_check_at": ..., "latest_known": ...}
    *.whl.tmp                     in-flight downloads

Concurrency: strategies.YtDlpStrategy wraps each download in engine_in_use();
apply_update() only swaps modules when no download is active (bounded wait,
otherwise the new version simply applies on next app start via activate()).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import shutil
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

PYPI_JSON_URL = "https://pypi.org/pypi/yt-dlp/json"  # hardcoded project, never configurable
HTTP_TIMEOUT_SECONDS = 30
CHECK_THROTTLE_SECONDS = 3600  # at most one PyPI check per hour (stampede guard)
APPLY_WAIT_SECONDS = 30.0

_cond = threading.Condition()
_in_use = 0
_engine_base: Path | None = None  # <data_dir>/engine, set by activate()
_active_version: str | None = None  # version whose dir is on sys.path (None = bundled)
_active_dir: str | None = None
_updating = False

_VERSION_RE = re.compile(r"__version__\s*=\s*['\"]([^'\"]+)['\"]")


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for piece in version.split("."):
        digits = re.match(r"\d+", piece)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def _read_version_from_package_dir(package_parent: Path) -> str | None:
    version_file = package_parent / "yt_dlp" / "version.py"
    try:
        match = _VERSION_RE.search(version_file.read_text(encoding="utf-8"))
    except OSError:
        return None
    return match.group(1) if match else None


_bundled_version_cache: str | None = None


def bundled_version() -> str | None:
    """Version of the yt-dlp that shipped with the app (pip/Chaquopy).

    First tries reading version.py as text off sys.path (plain installs);
    Chaquopy ships packages inside an asset zip where that fails, so
    activate() also caches it via a real import taken BEFORE the engine dir
    goes on sys.path (see _cache_bundled_version_by_import).
    """
    global _bundled_version_cache
    if _bundled_version_cache:
        return _bundled_version_cache
    try:
        for entry in sys.path:
            if entry == _active_dir:
                continue
            candidate = Path(entry) / "yt_dlp" / "version.py"
            if candidate.is_file():
                match = _VERSION_RE.search(candidate.read_text(encoding="utf-8"))
                if match:
                    _bundled_version_cache = match.group(1)
                    return _bundled_version_cache
    except Exception:
        return None
    return None


def _cache_bundled_version_by_import() -> None:
    """Fallback for zip-packaged installs (Chaquopy): import the bundled
    yt_dlp — only ever called while the engine dir is NOT on sys.path — read
    its version, and purge the modules again so a later activate/apply swap
    isn't defeated by a stale sys.modules entry."""
    global _bundled_version_cache
    if _bundled_version_cache:
        return
    try:
        module = importlib.import_module("yt_dlp")
        version = getattr(getattr(module, "version", None), "__version__", None)
        if version:
            _bundled_version_cache = str(version)
    except Exception:
        pass
    finally:
        _purge_yt_dlp_modules()


def active_version() -> str | None:
    """Version currently in effect (downloaded engine if active, else bundled)."""
    return _active_version or bundled_version()


def is_newer(candidate: str, baseline: str) -> bool:
    """True if `candidate` is a strictly newer version than `baseline`.

    Numeric-tuple comparison, not string equality: PyPI's JSON reports
    versions like "2026.7.4" while yt-dlp's own version.py (and thus
    active_version()/bundled_version()) reports the zero-padded "2026.07.04"
    for the same release. A plain string compare treated those as different,
    so /api/engine always claimed "update available" even when already
    current (caught on-device: the settings screen showed an update offer
    that never went away after applying it).
    """
    return _version_tuple(candidate) > _version_tuple(baseline)


def is_updating() -> bool:
    return _updating


@contextmanager
def engine_in_use():
    """Wrapped around every yt-dlp download so apply_update never swaps
    modules out from under a running transfer."""
    global _in_use
    with _cond:
        _in_use += 1
    try:
        yield
    finally:
        with _cond:
            _in_use -= 1
            _cond.notify_all()


def get_yt_dlp():
    """The current yt_dlp module. Import happens here (never at a caller's
    module top) so activate()'s sys.path change and apply_update()'s module
    purge are actually observed by the next download."""
    with _cond:
        import yt_dlp

        return yt_dlp


def activate(data_dir: Path | str) -> str | None:
    """Put the newest validated downloaded engine (if any) on sys.path.

    Must run before the first yt_dlp import to take effect immediately;
    thanks to get_yt_dlp()'s lazy import that just means "early in process
    start" (android_entry.start / create_server), not import order magic.
    Returns the activated version, or None when staying on the bundled one.
    """
    global _engine_base, _active_version, _active_dir
    base = Path(data_dir) / "engine"
    with _cond:
        _engine_base = base
        # Engine dir isn't on sys.path yet - the perfect (only) moment to
        # learn the bundled version on zip-packaged installs (Chaquopy).
        # MUST run unconditionally, before the current.json check below: on
        # a fresh install (no self-update ever downloaded) current.json
        # doesn't exist yet, and that used to short-circuit this entirely -
        # active_version()/bundled_version() stayed None for the process's
        # whole lifetime even though yt-dlp itself worked fine (caught by
        # download_pipeline_test.sh's /api/engine check on a real device).
        if bundled_version() is None:
            _cache_bundled_version_by_import()
        current = _read_json(base / "current.json")
        if not current:
            return None
        version = str(current.get("version") or "")
        rel_path = str(current.get("path") or "")
        engine_dir = base / rel_path
        on_disk = _read_version_from_package_dir(engine_dir)
        if not version or on_disk != version:
            # Corrupt/half-written state: forget it, bundled engine takes over.
            _safe_unlink(base / "current.json")
            return None
        bundled = bundled_version()
        if bundled and _version_tuple(version) <= _version_tuple(bundled):
            # The app update shipped a newer engine than our download - the
            # downloaded copy is obsolete, drop it.
            _safe_unlink(base / "current.json")
            return None
        if _active_dir and _active_dir in sys.path:
            sys.path.remove(_active_dir)
        sys.path.insert(0, str(engine_dir))
        _active_dir = str(engine_dir)
        _active_version = version
        return version


def read_state() -> dict:
    if _engine_base is None:
        return {}
    return _read_json(_engine_base / "state.json") or {}


def check_latest() -> tuple[str, str, str]:
    """(version, wheel_url, sha256) of the newest yt-dlp on PyPI."""
    with urllib.request.urlopen(PYPI_JSON_URL, timeout=HTTP_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    version = str(data["info"]["version"])
    for file_info in data.get("urls", []):
        filename = str(file_info.get("filename", ""))
        if filename.endswith("py3-none-any.whl"):
            url = str(file_info["url"])
            sha256 = str(file_info.get("digests", {}).get("sha256", ""))
            if not url.startswith("https://") or not sha256:
                break
            return version, url, sha256
    raise RuntimeError("No py3-none-any wheel with a sha256 digest found on PyPI")


def download_and_install(version: str, url: str, sha256: str) -> Path:
    """Fetch + verify + extract a wheel; flips current.json atomically.

    Raises on any validation failure; never leaves a half-installed engine
    referenced by current.json.
    """
    if _engine_base is None:
        raise RuntimeError("engine_update.activate() was never called")
    floor = active_version()
    if floor and _version_tuple(version) <= _version_tuple(floor):
        raise RuntimeError(f"Refusing downgrade/sidegrade: {version} <= active {floor}")

    _engine_base.mkdir(parents=True, exist_ok=True)
    tmp_path = _engine_base / f"yt_dlp-{version}.whl.tmp"
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response, tmp_path.open("wb") as out:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != sha256.lower():
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError("Wheel checksum mismatch - refusing to install")

    import zipfile

    target = _engine_base / f"yt_dlp-{version}"
    staging = _engine_base / f"yt_dlp-{version}.staging"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        with zipfile.ZipFile(tmp_path) as wheel:
            for entry in wheel.namelist():
                # Only the package itself; wheels also carry *.dist-info.
                if not entry.startswith("yt_dlp/"):
                    continue
                entry_path = Path(entry)
                if entry_path.is_absolute() or ".." in entry_path.parts:
                    raise RuntimeError(f"Wheel contains a suspicious path: {entry!r}")
                wheel.extract(entry, staging)
        if _read_version_from_package_dir(staging) != version:
            raise RuntimeError("Extracted wheel's version.py does not match the advertised version")
        shutil.rmtree(target, ignore_errors=True)
        staging.replace(target)
    finally:
        tmp_path.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)

    payload = json.dumps({"version": version, "path": target.name})
    tmp_json = _engine_base / "current.json.tmp"
    tmp_json.write_text(payload, encoding="utf-8")
    tmp_json.replace(_engine_base / "current.json")
    _prune_old_engines(keep=target.name)
    return target


def apply_update() -> bool:
    """Swap the freshly-installed engine into the running process.

    Waits (bounded) for zero active downloads, purges yt_dlp from
    sys.modules, adjusts sys.path, and verifies the new import — reverting
    completely on any failure. Returns True when the swap happened; False
    means "installed, applies on next app start" (activate() will pick it up).
    """
    global _active_version, _active_dir
    if _engine_base is None:
        return False
    current = _read_json(_engine_base / "current.json")
    if not current:
        return False
    version = str(current.get("version") or "")
    engine_dir = str(_engine_base / str(current.get("path") or ""))

    with _cond:
        if version == _active_version:
            return True
        if not _cond.wait_for(lambda: _in_use == 0, timeout=APPLY_WAIT_SECONDS):
            return False

        previous_dir = _active_dir
        previous_version = _active_version
        _purge_yt_dlp_modules()
        if previous_dir and previous_dir in sys.path:
            sys.path.remove(previous_dir)
        sys.path.insert(0, engine_dir)
        try:
            module = importlib.import_module("yt_dlp")
            imported = getattr(getattr(module, "version", None), "__version__", None) or getattr(
                module, "__version__", None
            )
            if imported != version:
                raise ImportError(f"Imported yt-dlp reports {imported!r}, expected {version!r}")
            _active_dir = engine_dir
            _active_version = version
            return True
        except Exception:
            # Full revert: never leave the process without a working engine.
            if engine_dir in sys.path:
                sys.path.remove(engine_dir)
            _purge_yt_dlp_modules()
            if previous_dir:
                sys.path.insert(0, previous_dir)
            _active_dir = previous_dir
            _active_version = previous_version
            importlib.import_module("yt_dlp")  # re-import previous/bundled
            return False


def ensure_latest(force: bool = False) -> tuple[bool, str | None]:
    """Check PyPI (throttled) and install+apply anything newer.

    Returns (installed_something_new, latest_version_seen). Safe to call
    from multiple failing download threads at once — the throttle plus the
    condition lock make it effectively single-flight.
    """
    global _updating
    if _engine_base is None:
        return False, None

    with _cond:
        if _updating:
            return False, read_state().get("latest_known")
        state = read_state()
        last_check = float(state.get("last_check_at") or 0.0)
        if not force and time.time() - last_check < CHECK_THROTTLE_SECONDS:
            return False, state.get("latest_known")
        _updating = True

    try:
        version, url, sha256 = check_latest()
        _write_state({"last_check_at": time.time(), "latest_known": version})
        floor = active_version()
        if floor and _version_tuple(version) <= _version_tuple(floor):
            return False, version
        download_and_install(version, url, sha256)
        apply_update()  # best effort; False just means "next start"
        return True, version
    except Exception:
        # Network down, PyPI hiccup, checksum problem - the bundled/current
        # engine keeps working; nothing to surface beyond the event log.
        try:
            _write_state({"last_check_at": time.time(), "latest_known": read_state().get("latest_known")})
        except Exception:
            pass
        return False, read_state().get("latest_known")
    finally:
        with _cond:
            _updating = False


def _purge_yt_dlp_modules() -> None:
    for name in [m for m in sys.modules if m == "yt_dlp" or m.startswith("yt_dlp.")]:
        sys.modules.pop(name, None)


def _prune_old_engines(keep: str) -> None:
    if _engine_base is None:
        return
    active_name = Path(_active_dir).name if _active_dir else ""
    for path in _engine_base.glob("yt_dlp-*"):
        if path.is_dir() and path.name not in (keep, active_name):
            shutil.rmtree(path, ignore_errors=True)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_state(state: dict) -> None:
    if _engine_base is None:
        return
    self_path = _engine_base / "state.json"
    _engine_base.mkdir(parents=True, exist_ok=True)
    tmp = _engine_base / "state.json.tmp"
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(self_path)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _reset_for_tests() -> None:
    """Test hook: forget all module state (never called in production)."""
    global _engine_base, _active_version, _active_dir, _updating, _in_use, _bundled_version_cache
    with _cond:
        if _active_dir and _active_dir in sys.path:
            sys.path.remove(_active_dir)
        _engine_base = None
        _active_version = None
        _active_dir = None
        _updating = False
        _in_use = 0
        _bundled_version_cache = None
    _purge_yt_dlp_modules()
