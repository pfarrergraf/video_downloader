from __future__ import annotations

from types import SimpleNamespace

from video_downloader import cli
from video_downloader import easy_ui


def test_legacy_detection_for_plain_url() -> None:
    assert cli._should_use_legacy_mode(["https://example.com/video"])


def test_subcommand_detection() -> None:
    assert not cli._should_use_legacy_mode(["download", "https://example.com/video"])


def test_ui_subcommand_detection_is_not_legacy() -> None:
    assert not cli._should_use_legacy_mode(["ui"])


def test_ui_subcommand_detection_is_case_insensitive() -> None:
    assert not cli._should_use_legacy_mode(["UI"])


def test_download_parser_keeps_profile_defaults_without_override() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["download", "https://example.com/video"])
    assert args.format_selector is None


def test_legacy_parser_still_accepts_old_invocation() -> None:
    parser = cli._build_legacy_parser()
    args = parser.parse_args(["https://example.com/video", "--max-items", "2"])
    assert args.url == "https://example.com/video"
    assert args.max_items == 2


def test_queue_reprioritize_parser_contract() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["queue", "reprioritize", "42", "--priority", "15"])
    assert args.command == "queue"
    assert args.queue_command == "reprioritize"
    assert args.job_id == 42
    assert args.priority == 15


def test_easy_ui_direct_main_uses_config_defaults(monkeypatch, tmp_path) -> None:
    captured: dict[str, str | None] = {}

    monkeypatch.setattr(easy_ui, "resolve_paths", lambda: object())
    monkeypatch.setattr(
        easy_ui,
        "load_or_create_config",
        lambda _paths: SimpleNamespace(default_output_dir=str(tmp_path / "downloads")),
    )
    monkeypatch.setattr(
        easy_ui,
        "run_easy_ui",
        lambda default_output_dir, initial_method, initial_cookies_from_browser: captured.update(
            {
                "output": default_output_dir,
                "method": initial_method,
                "cookies": initial_cookies_from_browser,
            }
        ),
    )

    result = easy_ui.main(["--method", "ffmpeg", "--cookies-from-browser", "chrome"])

    assert result == 0
    assert captured["output"] == str((tmp_path / "downloads").resolve())
    assert captured["method"] == "ffmpeg"
    assert captured["cookies"] == "chrome"
