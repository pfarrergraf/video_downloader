from __future__ import annotations

from scripts.playlist_canary import configured_urls, run_canary


class FakeYoutubeDL:
    options = None

    def __init__(self, options):
        type(self).options = options

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, source, download=False):
        assert download is False
        return {"title": "fixture", "entries": [{"id": "one"}, None, {"id": "two"}]}


def test_configured_urls_prefers_cli_then_environment(monkeypatch) -> None:
    monkeypatch.setenv("CLASSYDL_CANARY_URLS", "https://youtube.com/playlist?list=env")
    assert configured_urls([" https://youtube.com/playlist?list=cli "]) == [
        "https://youtube.com/playlist?list=cli"
    ]
    assert configured_urls() == ["https://youtube.com/playlist?list=env"]


def test_canary_is_flat_and_tolerates_skipped_entries(monkeypatch, capsys) -> None:
    monkeypatch.setattr("scripts.playlist_canary.shutil.which", lambda name: "/usr/bin/node")

    total = run_canary(
        ["https://www.youtube.com/watch?v=abc&list=PLfixture"],
        playlist_end=10,
        min_items=2,
        ytdl_factory=FakeYoutubeDL,
    )

    assert total == 2
    assert FakeYoutubeDL.options["extract_flat"] is True
    assert FakeYoutubeDL.options["skip_download"] is True
    assert "2 item(s), 1 skipped" in capsys.readouterr().out
