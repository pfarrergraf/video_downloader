from __future__ import annotations

from pathlib import Path

from video_downloader import android_entry


def test_start_wires_store_and_output_dir(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_run_server(*, store, output_dir, password, host, port, workers, ffmpeg_binary):
        captured["store"] = store
        captured["output_dir"] = output_dir
        captured["password"] = password
        captured["host"] = host
        captured["port"] = port
        captured["workers"] = workers
        captured["ffmpeg_binary"] = ffmpeg_binary

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
