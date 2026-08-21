# DownloadThat compatibility matrix

This is an internal, time-stamped interoperability test. It does not advertise
or guarantee support for any named service. The public catalog contains domains
only; exact URLs, adult-content references, raw errors and downloaded media are
kept below git-ignored `compatibility/private/` and `compatibility/results/`.

The main 200-domain runner uses the normal `DownloadManager` auto path without
authentication, cookies, custom headers, DRM keys or decryption. A success requires a completed
file with a valid audio/video stream reported by `ffprobe`. Every temporary media
file is deleted immediately after the attempt.

The tracked `REPORT_2026-08-21.md` is the URL-free, shareable aggregate. Raw
URLs and error messages remain private and ignored by Git.

Windows PowerShell commands (from the repository root):

```powershell
uv venv .compat-venv --python 3.11
uv pip install --python .compat-venv\Scripts\python.exe -e ".[dev]"
.compat-venv\Scripts\python.exe scripts\generate_compatibility_catalog.py
.compat-venv\Scripts\python.exe scripts\run_compatibility_matrix.py prepare
.compat-venv\Scripts\python.exe scripts\run_compatibility_matrix.py validate
.compat-venv\Scripts\python.exe scripts\run_compatibility_matrix.py run --workers 6
```

If `prepare` reports missing slots, add only public, canonical single-media URLs
to the private `compatibility/private/url_overrides.json` mapping. Do not add
piracy sites, credentials, cookies, manifests, license endpoints or DRM tooling.

Android evidence is a separate gate. It remains pending until an `adb`-visible
device/emulator is available; Windows engine results must not be relabeled as
Android device results.

## Sichtbare Belegdownloads und Login-Gegenprobe

The normal matrix deletes media after validation. To retain inspectable proof,
re-run selected public, non-adult, non-DRM cases with `verify --keep-successes`.
The retained files and their SHA-256 evidence stay below the git-ignored
`compatibility/results/` directory:

```powershell
.compat-venv\Scripts\python.exe scripts\run_compatibility_matrix.py verify --domains youtube.com --url-index 1 --keep-successes
```

Authenticated checks are separate from the anonymous matrix. First sign in to
the services in a local supported browser. Then explicitly select that browser;
the runner passes only its name to DownloadThat's existing
`cookies_from_browser` path. It does not export or serialize cookies:

```powershell
.compat-venv\Scripts\python.exe scripts\run_compatibility_matrix.py verify --domains youtube.com,tiktok.com,facebook.com --cookies-from-browser edge --keep-successes
```

Close the selected browser completely before starting; Chromium browsers lock
their cookie database even when only a background process remains. The runner
now checks this once up front and aborts instead of producing one misleading
platform failure per URL. Results are
written separately as `verification/evidence-anonymous.jsonl` and
`verification/evidence-authenticated.jsonl`; authenticated success never
overwrites or upgrades the anonymous public claim. Retention is refused for
adult and DRM/subscription categories even if a file is returned.
