"""Tracks whether this install has a valid DownloadThat Pro license.

Talks to the license-verification endpoint (GET /api/validate?key=... —
see pro/website/functions/api/validate.js, a Cloudflare Pages Function on
the same deployment as the marketing site, not a separate Worker) at most
once every CACHE_TTL_SECONDS, and keeps trusting the last successful result
for up to OFFLINE_GRACE_SECONDS if the phone has no connectivity, so a brief
network outage doesn't downgrade a paying user mid-session.

Deliberately opt-in: when no api_base is configured (Termux, desktop, CLI,
tests), `LicenseManager` isn't constructed at all and callers treat that as
"always Pro" — the free/open core stays fully unrestricted on every platform
except the distributed Android app, which is the only thing being sold.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

# Free tier: same quality as Pro, just rationed — 1 download per rolling
# 24h window (not calendar-day, so there's no "download at 23:59, download
# again at 00:01" loophole). Pro: no quota at all. See web/server.py's
# _recent_job_count for how this is enforced.
FREE_DAILY_DOWNLOAD_LIMIT = 5
FREE_WINDOW_HOURS = 24
CACHE_TTL_SECONDS = 6 * 3600
OFFLINE_GRACE_SECONDS = 7 * 24 * 3600


@dataclass(slots=True)
class LicenseState:
    key: str | None = None
    valid: bool = False
    tier: str | None = None
    checked_at: float = 0.0

    @property
    def is_pro(self) -> bool:
        return self.valid


class LicenseManager:
    def __init__(self, state_file: Path, api_base: str) -> None:
        self._state_file = state_file
        self._api_base = api_base.rstrip("/")
        self._state = self._load()

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

    def status(self) -> LicenseState:
        return self._state

    def is_pro(self) -> bool:
        self.refresh()
        return self._state.is_pro

    def set_key(self, key: str) -> LicenseState:
        self._state = LicenseState(key=key)
        self.refresh(force=True)
        return self._state

    def refresh(self, *, force: bool = False) -> LicenseState:
        if not self._state.key:
            return self._state
        if not force and time.time() - self._state.checked_at < CACHE_TTL_SECONDS:
            return self._state
        try:
            response = requests.get(
                f"{self._api_base}/api/validate", params={"key": self._state.key}, timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            # Offline or the license server is unreachable: keep trusting a
            # recent "valid" result rather than instantly cutting the user
            # off, but don't extend that trust indefinitely.
            if time.time() - self._state.checked_at > OFFLINE_GRACE_SECONDS:
                self._state = LicenseState(key=self._state.key, valid=False, checked_at=self._state.checked_at)
                self._save()
            return self._state

        self._state = LicenseState(
            key=self._state.key,
            valid=bool(data.get("valid")),
            tier=data.get("tier"),
            checked_at=time.time(),
        )
        self._save()
        return self._state
