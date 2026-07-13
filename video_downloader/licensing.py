"""Tracks whether this install has a valid DownloadThat Pro license.

Talks to the license-verification endpoint (GET /api/validate?key=... —
see pro/website/functions/api/validate.js, a Cloudflare Pages Function on
the same deployment as the marketing site, not a separate Worker) at most
once every CACHE_TTL_SECONDS, and keeps trusting the last successful result
for up to OFFLINE_GRACE_SECONDS if the device has no connectivity, so a brief
network outage doesn't downgrade a paying user mid-session.

Free tier and Pro are intentionally cross-platform product rules: distributed
Android and desktop builds both enforce the same 3-download rolling 24h free
quota; the same Pro license key should unlock Android, Windows desktop, and
future macOS/iOS/Linux builds. Developer-only/debug paths may still opt out by
not constructing a LicenseManager, but shipped customer builds should wire it
up to the production license API.

The same key can still only be *actively used* on one device per platform at
a time (one Android slot, one Windows slot, etc.) - pass `platform=` (and
optionally `app_version=`) when constructing a LicenseManager to opt into
this. The server (pro/website/functions/api/validate.js) tracks device slots
by a random per-install `device_id` (never a hardware identifier) and returns
`device_allowed: false` once a different device already holds that
platform's slot; `LicenseState.is_pro` folds that into the usual valid/expired
check. Leaving `platform` empty (the default) skips this entirely, which is
why Termux/desktop-CLI callers that construct LicenseManager without it are
unaffected.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

# Free tier: same quality as Pro, just rationed — 3 downloads per rolling
# 24h window (not calendar-day, so there's no "download at 23:59, download
# again at 00:01" loophole). Pro: no quota at all. See web/server.py's
# _recent_job_count for how this is enforced.
FREE_DAILY_DOWNLOAD_LIMIT = 3
FREE_WINDOW_HOURS = 24
CACHE_TTL_SECONDS = 6 * 3600
OFFLINE_GRACE_SECONDS = 7 * 24 * 3600


@dataclass(slots=True)
class LicenseState:
    key: str | None = None
    valid: bool = False
    tier: str | None = None
    checked_at: float = 0.0
    # Random per-install identifier, never the raw device hardware ID -
    # generated once and persisted so the same install keeps its slot across
    # restarts. Sent to /api/validate (hashed server-side) to enforce the
    # one-active-device-per-platform policy; see docs/DESKTOP_WEB_UI_PLAN.md.
    device_id: str | None = None
    # Whether *this* device currently holds the platform's activation slot
    # for this key. Defaults True so installs that predate this field (or a
    # manager constructed without a platform) are never held back by it.
    device_allowed: bool = True

    @property
    def is_pro(self) -> bool:
        return self.valid and self.device_allowed


class LicenseManager:
    def __init__(self, state_file: Path, api_base: str, *, platform: str = "", app_version: str = "") -> None:
        # Empty platform (the default, used by Termux/desktop-CLI callers that
        # never wire this up) means the device-limit check below is skipped
        # entirely - only shipped Android/desktop builds should pass this.
        self._state_file = state_file
        self._api_base = api_base.rstrip("/")
        self._platform = platform
        self._app_version = app_version
        self._state = self._load()
        if self._platform and not self._state.device_id:
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
        # Holds the license key + device id; keep it owner-only so a co-tenant
        # can't lift the key. Best-effort (advisory on Windows).
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
        self._state = LicenseState(key=key, device_id=self._state.device_id)
        self.refresh(force=True)
        return self._state

    def refresh(self, *, force: bool = False) -> LicenseState:
        if not self._state.key:
            return self._state
        if not force and time.time() - self._state.checked_at < CACHE_TTL_SECONDS:
            return self._state
        params = {"key": self._state.key}
        if self._platform and self._state.device_id:
            params["platform"] = self._platform
            params["device_id"] = self._state.device_id
            if self._app_version:
                params["app_version"] = self._app_version
        try:
            response = requests.get(f"{self._api_base}/api/validate", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            # Offline or the license server is unreachable: keep trusting a
            # recent "valid" result rather than instantly cutting the user
            # off, but don't extend that trust indefinitely.
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
        )
        self._save()
        return self._state
