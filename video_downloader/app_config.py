from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass(slots=True)
class AppPaths:
    config_file: Path
    state_db: Path
    log_dir: Path
    log_file: Path


@dataclass(slots=True)
class AppConfig:
    default_output_dir: str
    default_workers: int = 3
    max_workers: int = 8
    legal_warning_ack: bool = False


def resolve_paths() -> AppPaths:
    override = os.environ.get("CLASSYDL_DATA_DIR")
    if override:
        root = Path(override).expanduser()
        return AppPaths(
            config_file=root / "config.toml",
            state_db=root / "state.db",
            log_dir=root / "logs",
            log_file=root / "logs" / "classydl.log",
        )

    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    localappdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))

    roaming_root = appdata / "ClassyDL"
    local_root = localappdata / "ClassyDL"
    return AppPaths(
        config_file=roaming_root / "config.toml",
        state_db=local_root / "state.db",
        log_dir=local_root / "logs",
        log_file=local_root / "logs" / "classydl.log",
    )


def _harden(path: Path, mode: int) -> None:
    """Best-effort restrictive permissions. No-op / advisory on Windows, where
    POSIX modes don't apply - the data-dir there is already per-user under
    %APPDATA%/%LOCALAPPDATA%. On Linux/Termux this stops a co-tenant local
    user reading the state DB, config, logs, and secrets."""
    try:
        path.chmod(mode)
    except OSError:
        pass


def ensure_runtime_paths(paths: AppPaths) -> None:
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.state_db.parent.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    # Directories owner-only (0700) so the files inside them - state.db,
    # config.toml, logs, web_password.txt, license.json - aren't world-listable.
    _harden(paths.config_file.parent, 0o700)
    _harden(paths.state_db.parent, 0o700)
    _harden(paths.log_dir, 0o700)


def default_config() -> AppConfig:
    default_output = Path.home() / "Downloads" / "ClassyDL"
    return AppConfig(default_output_dir=str(default_output), default_workers=3, max_workers=8)


def load_or_create_config(paths: AppPaths) -> AppConfig:
    ensure_runtime_paths(paths)
    if not paths.config_file.exists():
        config = default_config()
        save_config(paths, config)
        return config

    raw = paths.config_file.read_bytes()
    try:
        parsed = tomllib.loads(raw.decode("utf-8"))
    except Exception:
        config = default_config()
        save_config(paths, config)
        return config

    app_section = parsed.get("app", {})
    config = default_config()
    config.default_output_dir = str(app_section.get("default_output_dir", config.default_output_dir))
    config.default_workers = _clamp_int(app_section.get("default_workers", config.default_workers), 1, 8)
    config.max_workers = _clamp_int(app_section.get("max_workers", config.max_workers), 1, 16)
    if config.default_workers > config.max_workers:
        config.default_workers = config.max_workers
    config.legal_warning_ack = bool(app_section.get("legal_warning_ack", False))
    return config


def save_config(paths: AppPaths, config: AppConfig) -> None:
    ensure_runtime_paths(paths)
    lines = [
        "[app]",
        f'default_output_dir = "{_escape(config.default_output_dir)}"',
        f"default_workers = {int(config.default_workers)}",
        f"max_workers = {int(config.max_workers)}",
        f"legal_warning_ack = {str(bool(config.legal_warning_ack)).lower()}",
        "",
    ]
    paths.config_file.write_text("\n".join(lines), encoding="utf-8")
    _harden(paths.config_file, 0o600)


def _clamp_int(value: object, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return lower
    return max(lower, min(upper, parsed))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
