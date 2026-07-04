# Desktop version of the Gothic web UI — implementation plan

Written for a fresh agent (no prior context on this project) to pick up and
execute. Read `CLAUDE.md` first — it documents hard constraints that apply
here too (stdlib-only web server, pure-Python dependencies, etc.).

## Goal

Ship a standalone Windows executable that opens the same "Gothic" web UI
already used by the Android app (`video_downloader/web/server.py` +
`video_downloader/web/static/index.html`) — no separate GUI toolkit window,
just: double-click the exe, the local server starts, the user's default
browser opens to it, already logged in. No Python install required by the
end user. Mac support is a later phase (see bottom).

## What already exists — don't rebuild this

1. **The web UI itself** is already finished, tested, and cross-platform: it's
   plain HTML/CSS/JS served by a stdlib-only `http.server` (see
   `video_downloader/web/server.py`'s module docstring for why — no
   FastAPI/uvicorn/pydantic). It already runs on any desktop OS today via
   `classydl web` (see `video_downloader/cli.py`'s `_command_web`,
   `CLASSYDL_WEB_PASSWORD` env var). Nothing about the UI needs to change for
   desktop — it's the *packaging* that's missing.

2. **A working PyInstaller pipeline already exists on `master`** (and is
   present unchanged in this branch too — verified via
   `git diff origin/master...HEAD -- classydl.spec classydl_entry.py
   scripts/build_windows.ps1` returning empty). It currently packages the
   *other* desktop front-end, the Tkinter GUI (`video_downloader/easy_ui.py`),
   into a standalone `classydl.exe`. Read
   `.github/instructions/pyinstaller.instructions.md` in full before touching
   any of this — it documents several hard-won lessons (windowed app + no
   console = silent failures if you get this wrong, UPX must stay disabled,
   `freeze_support()` is required, bundled binaries need to be prepended to
   `PATH` at runtime). Relevant existing files:
   - `classydl.spec` — PyInstaller spec, entry point `classydl_entry.py`
   - `classydl_entry.py` — sets up `sys._MEIPASS/bundled_bins` on `PATH`,
     wraps `main()` in a try/except that shows a Tkinter crash dialog if the
     app is frozen and something raises (there's no console to print to)
   - `scripts/build_windows.ps1` — build script, has a `-BundleAll` flag that
     copies ffmpeg/aria2c from PATH into `bundled_bins/` before packaging
   - `scripts/selfsign_local.ps1` / `resign.ps1` / `import_trust.ps1` —
     self-signing so Windows SmartScreen doesn't block the exe

Do **not** replace or modify the Tkinter build target — add a second,
parallel one. Both should be able to coexist (`classydl.exe` and, say,
`classydl-web.exe`) until the project owner decides whether to deprecate the
Tkinter UI.

## What's missing

### 1. A new entry point: `classydl_web_entry.py`

Mirror `classydl_entry.py`'s structure (frozen-mode `bundled_bins` PATH setup,
`freeze_support()`, crash-dialog wrapper — reuse the same Tkinter
`messagebox.showerror` fallback for crash reporting even though this build
doesn't otherwise use Tkinter; it's the only thing guaranteed available for
showing an error with no console). Instead of calling `cli.main()`, it should:

1. Resolve data/output dirs via `video_downloader.app_config.resolve_paths()`
   (already handles the Windows `AppData/Roaming` path correctly — see
   `CLAUDE.md`'s note about `CLASSYDL_DATA_DIR` — don't reinvent this).
2. Generate-or-load a per-install random password, persisted under the
   resolved data dir (same idea as `MainActivity.kt`'s
   `getOrCreatePassword()` on Android — mirror that logic: `SecureRandom`
   equivalent is `secrets.token_hex()`, store it in a file, reuse on
   subsequent launches).
3. Start the server (reuse `video_downloader.web.server.create_server` /
   whatever `_command_web` in `cli.py` already does — read that function
   first, don't duplicate its logic, factor out a shared helper if needed).
4. Open the system browser via `webbrowser.open(...)` pointed at the local
   server, **with the password embedded so the user never has to type it** —
   see "Auto-login" below for how.
5. Keep the process alive (the server runs on a background thread in the
   existing design — check how `classydl web` currently blocks/waits, mirror
   that).

**Port handling**: reuse a fixed port (e.g. 8420, matching Android's
`MainActivity.PORT`) rather than a random one — simpler to reason about, and
if binding fails because another instance is already running, catch that and
just open the browser to the existing instance instead of crashing.

### 2. Auto-login without a WebView

Android's `MainActivity.kt` auto-fills the login form via injected JS because
it controls a WebView. A desktop build launches the *system* browser, which
can't be scripted the same way. Instead:

- Open a short-lived local autologin bridge page, e.g.
  `http://127.0.0.1:8420/desktop_autologin.html?t=<password>`.
- That page posts the token to `/api/login`, strips the query from browser
  history with `history.replaceState`, then redirects to `/`.
- Keep the actual app page unchanged where possible; the bridge avoids a risky
  full rewrite of the large `static/index.html` file while preserving the same
  server-side auth/session behavior.

### 3. `classydl_web.spec`

Copy `classydl.spec`, change:
- `Analysis(['classydl_web_entry.py'], ...)`
- **Verify `video_downloader/web/static/**` (including `static/i18n/*.json`,
  `icon.svg`, `manifest.webmanifest`) actually gets bundled.** This is the
  single biggest risk in this plan — `pyproject.toml`'s
  `[tool.setuptools.package-data]` previously declared
  `"video_downloader.web" = ["static/*"]`, which is a **single-level glob**
  and will not match files inside `static/i18n/` (a subdirectory). Fix it to
  `"video_downloader.web" = ["static/**/*"]`, and keep an explicit PyInstaller
  `datas` entry for `video_downloader.web` static assets.
- Keep `console=False`, `upx=False` — same reasoning as the Tkinter build.

### 4. Build script

Either add a `-Target web` parameter to the existing
`scripts/build_windows.ps1`, or add a sibling `scripts/build_windows_web.ps1`
that shares the ffmpeg-bundling logic. **Whichever you pick, make sure the
bundled ffmpeg used for this build actually has MP3 encoding
(`--enable-libmp3lame` equivalent for Windows, e.g. a build with libmp3lame
statically linked, same requirement as the Android build in
`.github/scripts/build_ffmpeg_android.sh` — read that file for reference).**
There was a real bug (just fixed, see `video_downloader/strategies.py`'s
`YtDlpStrategy.download`) where audio-only downloads silently fell back to
the raw un-converted format when the ffmpeg binary in use couldn't encode
MP3 — don't reintroduce the same failure mode by bundling an ffmpeg without
mp3 support for this build. That fix now at least surfaces a warning instead
of failing silently (see `job.error` / the "details" flow through
`queue_store.py`'s `mark_job_completed`), so it's not silent anymore, but it's
better to just bundle a working ffmpeg from the start.

### 5. License gating — product decision now fixed

Desktop must share the same Freemium/Pro model as Android:

- Free tier: 3 downloads per rolling 24h window.
- Pro: unlimited downloads and Pro-only features such as playlist/batch flows.
- A Pro license key is cross-platform: the same key should unlock Android,
  Windows desktop, future macOS/iOS, and Linux builds.
- Desktop uses the same production validation API as Android:
  `https://downloadthat.pages.dev/api/validate`.
- The license state should be persisted under the resolved app data/config
  directory as `license.json`, matching the existing `LicenseManager` model.

Do not leave the shipped desktop app unrestricted. Developer/debug paths may
still bypass licensing when explicitly configured, but customer builds should
construct `LicenseManager` and pass it into `create_server`/`run_server`.

#### Device-limit policy, still to implement backend-side

The current client can validate one cross-platform license key, but the server
backend still needs an activation/device policy. Recommended product rule:

- 1 active Android phone/tablet slot
- 1 active Windows desktop/laptop slot
- 1 active macOS slot, later
- 1 active Linux slot, later
- 1 active iOS/iPadOS slot, later

This is easy for honest customers and prevents one key from being shared
widely. Implement with activation records in the Cloudflare D1/Stripe backend:
`license_key_hash`, `platform`, `device_id_hash`, `first_seen`, `last_seen`,
`app_version`, and `revoked_at`. The `/api/validate` endpoint should accept
`platform` and `device_id` later, then return whether that device slot is
allowed. Do not store raw device IDs if a hash is enough.

### 6. Tests

Add `tests/test_desktop_web_entry.py` (skip cleanly if `tkinter` isn't
importable, same pattern as `tests/test_easy_ui.py` / `test_cli_compat.py` —
see `CLAUDE.md`'s testing section for why that skip exists in this sandboxed
dev environment). Cover, with `webbrowser.open` and the actual server start
mocked out:
- Password is generated once and reused on a second "launch" (same data dir).
- The URL passed to `webbrowser.open` contains the autologin token.
- A bind failure (port already in use) doesn't crash — falls back to opening
  the browser to the existing instance.
- Desktop constructs a `LicenseManager` and passes it into the server.

For the autologin bridge, verify with a real server/browser flow: loading
`/desktop_autologin.html?t=<password>` lands on the authenticated app view and
the URL no longer contains the password afterward.

## Mac (later phase, not now)

PyInstaller supports macOS `.app` bundling with a similar spec-file approach,
but needs: code signing with an Apple Developer ID (costs money, requires an
Apple account) and notarization (a separate Apple service call after
signing) or Gatekeeper will block it outright — this is a materially
different and slower process than Windows self-signing. Treat as a fully
separate follow-up plan once Windows is verified working, not a "just add
another spec" afterthought.

## iPhone (not in scope here)

Explicitly out of scope for this plan — see the "Standalone Android app"
section of `CLAUDE.md` for why Android could use Chaquopy and why there's no
equivalent-maturity option for embedding this same Python codebase in an iOS
app. Revisit only after desktop ships.
