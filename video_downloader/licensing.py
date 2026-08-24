"""Tracks whether this install has a valid DownloadThat Pro license.

Talks to the license-verification endpoint (POST /api/license/validate —
see pro/website/functions/api/license/validate.js, a Cloudflare Pages Function on
the same deployment as the marketing site) at most once every
CACHE_TTL_SECONDS, and keeps trusting the last successful result for up to
OFFLINE_GRACE_SECONDS if the device has no connectivity.

Free tier and Pro are intentionally cross-platform product rules. The same key
can only be actively used on one device per platform at a time. Android release
builds pass a privacy-preserving, reinstall-stable device identifier derived in
Kotlin; desktop/CLI callers without an explicit device ID keep their persisted
random fallback.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

FREE_DAILY_DOWNLOAD_LIMIT = 3
FREE_WINDOW_HOURS = 24
CACHE_TTL_SECONDS = 6 * 3600
OFFLINE_GRACE_SECONDS = 72 * 3600
ANDROID_DEVICE_ID_SCHEME = "android-scoped-v1"


@dataclass(slots=True)
class LicenseState:
    key: str | None = None
    valid: bool = False
    tier: str | None = None
    checked_at: float = 0.0
    device_id: str | None = None
    device_allowed: bool = True
    expires_at: float | None = None

    @property
    def is_pro(self) -> bool:
        return (
            self.valid
            and self.device_allowed
            and (self.expires_at is None or self.expires_at > time.time())
        )


class LicenseManager:
    def __init__(
        self,
        state_file: Path,
        api_base: str,
        *,
        platform: str = "",
        app_version: str = "",
        device_id: str | None = None,
    ) -> None:
        self._state_file = state_file
        self._api_base = api_base.rstrip("/")
        self._platform = platform
        self._app_version = app_version
        self._state = self._load()
        self._device_id_scheme = ""

        if self._platform and device_id:
            if self._state.device_id != device_id:
                self._state.device_id = device_id
                self._save()
            if self._platform == "android":
                self._device_id_scheme = ANDROID_DEVICE_ID_SCHEME
        elif self._platform and not self._state.device_id:
            self._state.device_id = secrets.token_hex(16)
            self._save()

    def _load(self) -> LicenseState:
        try:
            data = json.loads(self._state_file.read_text())
        except (OSError, json.JSONDecodeError):
            return LicenseState()
        try:
            return LicenseState(**data)
        except TypeError:
            return LicenseState()

    def _save(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(asdict(self._state)))
        try:
            self._state_file.chmod(0o600)
        except OSError:
            pass

    def status(self) -> LicenseState:
        return self._state

    def is_pro(self) -> bool:
        self.refresh()
        return self._state.is_pro

    def set_key(self, key: str) -> LicenseState:
        # Re-applying the same key is an entitlement convergence operation,
        # not a fresh activation. Preserve the last verified state so a
        # transient network failure cannot erase a still-valid offline grace.
        if key != self._state.key:
            self._state = LicenseState(key=key, device_id=self._state.device_id)
        self.refresh(force=True)
        return self._state

    def clear_key(self) -> LicenseState:
        """Remove local entitlement while preserving this device identity."""
        self._state = LicenseState(device_id=self._state.device_id)
        self._save()
        return self._state

    def refresh(self, *, force: bool = False) -> LicenseState:
        if not self._state.key:
            return self._state
        if not force and time.time() - self._state.checked_at < CACHE_TTL_SECONDS:
            return self._state
        payload = {"key": self._state.key}
        if self._platform and self._state.device_id:
            payload["platform"] = self._platform
            payload["device_id"] = self._state.device_id
            if self._device_id_scheme:
                payload["device_id_scheme"] = self._device_id_scheme
            if self._app_version:
                payload["app_version"] = self._app_version
        try:
            response = requests.post(f"{self._api_base}/api/license/validate", json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            if time.time() - self._state.checked_at > OFFLINE_GRACE_SECONDS:
                self._state = LicenseState(
                    key=self._state.key,
                    valid=False,
                    device_id=self._state.device_id,
                    checked_at=self._state.checked_at,
                )
                self._save()
            return self._state

        self._state = LicenseState(
            key=self._state.key,
            valid=bool(data.get("valid")),
            tier=data.get("tier"),
            checked_at=time.time(),
            device_id=self._state.device_id,
            device_allowed=bool(data.get("device_allowed", True)),
            expires_at=data.get("expires_at"),
        )
        self._save()
        return self._state
