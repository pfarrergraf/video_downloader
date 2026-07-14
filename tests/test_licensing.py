from __future__ import annotations

import time
from pathlib import Path

import pytest
import requests

from video_downloader import licensing
from video_downloader.licensing import LicenseManager


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_no_key_is_never_pro(tmp_path: Path) -> None:
    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com")
    assert manager.is_pro() is False
    assert manager.status().key is None


def test_set_key_validates_against_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"valid": True, "tier": "lifetime"}))

    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com")
    state = manager.set_key("DLT-GOODKEY")

    assert state.valid is True
    assert state.tier == "lifetime"
    assert manager.is_pro() is True


def test_invalid_key_is_not_pro(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"valid": False}))

    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com")
    state = manager.set_key("DLT-BADKEY")

    assert state.valid is False
    assert manager.is_pro() is False


def test_state_persists_across_instances(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"valid": True, "tier": "yearly"}))
    state_file = tmp_path / "license.json"

    LicenseManager(state_file, "https://license.example.com").set_key("DLT-GOODKEY")

    # A fresh instance (e.g. after an app restart) reloads the cached result
    # without hitting the network again, since the TTL hasn't elapsed.
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")))
    reloaded = LicenseManager(state_file, "https://license.example.com")
    assert reloaded.is_pro() is True
    assert reloaded.status().tier == "yearly"


def test_network_error_keeps_trusting_recent_valid_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"valid": True, "tier": "monthly"}))
    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com")
    manager.set_key("DLT-GOODKEY")

    def boom(*a, **k):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", boom)
    # Force a re-check despite the TTL, simulating "still within the offline
    # grace period" — should keep trusting the last known-good result.
    state = manager.refresh(force=True)
    assert state.valid is True


def test_network_error_past_offline_grace_falls_back_to_free(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"valid": True, "tier": "monthly"}))
    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com")
    manager.set_key("DLT-GOODKEY")
    # Simulate the last successful check having happened long ago.
    manager._state.checked_at = time.time() - licensing.OFFLINE_GRACE_SECONDS - 1

    def boom(*a, **k):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", boom)
    state = manager.refresh(force=True)
    assert state.valid is False


def test_invalid_cached_json_is_ignored(tmp_path: Path) -> None:
    state_file = tmp_path / "license.json"
    state_file.write_text("not json")
    manager = LicenseManager(state_file, "https://license.example.com")
    assert manager.is_pro() is False


def test_no_platform_never_sends_device_params(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse({"valid": True, "tier": "lifetime"})

    monkeypatch.setattr(requests, "post", fake_post)
    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com")
    manager.set_key("DLT-GOODKEY")

    assert "platform" not in captured["payload"]
    assert "device_id" not in captured["payload"]
    assert manager.status().device_id is None


def test_platform_sends_a_persisted_device_id(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse({"valid": True, "tier": "lifetime", "device_allowed": True})

    monkeypatch.setattr(requests, "post", fake_post)
    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com", platform="android")
    device_id = manager.status().device_id
    assert device_id

    manager.set_key("DLT-GOODKEY")
    assert captured["payload"]["platform"] == "android"
    assert captured["payload"]["device_id"] == device_id
    assert manager.is_pro() is True


def test_device_not_allowed_is_not_pro_even_if_key_valid(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: FakeResponse({"valid": True, "tier": "yearly", "device_allowed": False})
    )
    manager = LicenseManager(tmp_path / "license.json", "https://license.example.com", platform="windows")
    state = manager.set_key("DLT-GOODKEY")

    assert state.valid is True
    assert state.device_allowed is False
    assert state.is_pro is False
    assert manager.is_pro() is False


def test_device_id_survives_set_key_and_reload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"valid": True, "tier": "lifetime"}))
    state_file = tmp_path / "license.json"
    manager = LicenseManager(state_file, "https://license.example.com", platform="android")
    device_id = manager.status().device_id

    manager.set_key("DLT-GOODKEY")
    assert manager.status().device_id == device_id

    reloaded = LicenseManager(state_file, "https://license.example.com", platform="android")
    assert reloaded.status().device_id == device_id
