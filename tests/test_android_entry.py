from __future__ import annotations

from pathlib import Path

from video_downloader import android_entry


def test_start_wires_store_and_output_dir(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_run_server(*, store, output_dir, password, host, port, workers, ffmpeg_binary, license_manager):
        captured["store"] = store
        captured["output_dir"] = output_dir
        captured["password"] = password
        captured["host"] = host
        captured["port"] = port
        captured["workers"] = workers
        captured["ffmpeg_binary"] = ffmpeg_binary
        captured["license_manager"] = license_manager

    monkeypatch.setattr(android_entry, "run_server", fake_run_server)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "downloads"
    android_entry.start(str(data_dir), str(output_dir), "secret", 8420, "/opt/bin/ffmpeg")

    assert (data_dir / "state.db").exists()
    assert captured["output_dir"] == output_dir
    assert captured["password"] == "secret"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8420
    assert captured["ffmpeg_binary"] == "/opt/bin/ffmpeg"
    assert captured["license_manager"] is None  # no license_api_base passed -> licensing off


def test_start_wires_license_manager_when_api_base_given(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_run_server(*, license_manager, **_ignored):
        captured["license_manager"] = license_manager

    monkeypatch.setattr(android_entry, "run_server", fake_run_server)

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "downloads"
    android_entry.start(
        str(data_dir), str(output_dir), "secret", 8420, "ffmpeg", "https://license.example.com"
    )

    manager = captured["license_manager"]
    assert manager is not None
    assert manager.status().valid is False


def test_publish_to_downloads_is_a_noop_without_the_java_bridge(tmp_path: Path) -> None:
    # Off-Android (this sandbox, CI, Termux, desktop) there is no `java` module
    # to import, so publishing must silently do nothing rather than error.
    output = tmp_path / "video.mp4"
    output.write_bytes(b"data")

    android_entry._publish_file_to_downloads(output)

    assert not android_entry._already_published(output)


def test_publish_marker_roundtrip(tmp_path: Path) -> None:
    output = tmp_path / "video.mp4"
    output.write_bytes(b"data")

    assert not android_entry._already_published(output)
    android_entry._mark_published(output)
    assert android_entry._already_published(output)
