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

- Pass the password as a URL query parameter when opening the browser:
  `http://127.0.0.1:8420/?autologin=<password>`.
- In `video_downloader/web/static/index.html`, near where `checkAuth()` is
  first called on page load, check for `?autologin=` in
  `location.search`. If present, submit it to `/api/login` immediately
  (same code path as the existing `$('login-btn')` handler) and strip it from
  the URL afterward with `history.replaceState` (don't leave a plaintext
  password sitting in the address bar / browser history).
- **Reuse the existing `authGeneration` counter** (see the comment above it
  in `static/index.html`) when wiring this in — same class of race this
  counter already exists to prevent (a stale `checkAuth()` resolving after
  this auto-login already succeeded). Increment it right before calling
  `setAuthed(true)` here too, exactly like the existing login button handler
  does.
- This is a small, generic change (not desktop-specific in the code itself),
  so it works identically if `classydl web` is later given the same
  "open browser with token" treatment on Linux/Mac.

### 3. `classydl_web.spec`

Copy `classydl.spec`, change:
- `Analysis(['classydl_web_entry.py'], ...)`
- **Verify `video_downloader/web/static/**` (including `static/i18n/*.json`,
  `icon.svg`, `manifest.webmanifest`) actually gets bundled.** This is the
  single biggest risk in this plan — `pyproject.toml`'s
  `[tool.setuptools.package-data]` currently declares
  `"video_downloader.web" = ["static/*"]`, which is a **single-level glob**
  and will not match files inside `static/i18n/` (a subdirectory). Whether
  PyInstaller's `collect_all('video_downloader')` picks up the i18n JSON
  files anyway depends on whether it walks the actual on-disk package
  directory or trusts the wheel's declared package-data metadata — don't
  assume either way. **Build once, then actually inspect
  `dist/classydl-web/_internal/video_downloader/web/static/` (or wherever
  PyInstaller puts it) and confirm `static/i18n/*.json` is there.** If it's
  missing, fix `pyproject.toml` to `"video_downloader.web" = ["static/**/*"]`
  first (this would also be a real bug for plain `pip install`/wheel users
  today, independent of this desktop-packaging work — worth its own small fix
  either way), and/or add an explicit `datas` entry in the spec for
  `video_downloader/web/static`.
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

### 5. License gating — needs a product decision, not an engineering one

`video_downloader/licensing.py`'s `LicenseManager` is currently only wired up
on Android (`MainActivity.kt` passes `LICENSE_API_BASE`; the CLI/web/Termux
paths pass `license_api_base=""`, which means "licensing off, always
unrestricted" — see the licensing.py module docstring). Before wiring
anything up here, get an explicit answer from the project owner on:

- Should the desktop build be fully unrestricted (free tool, Android is the
  only thing being sold), matching how `classydl web` already behaves today?
- Or should it share the same free-tier-3-downloads/Pro-unlocks-it model as
  Android?
- If the latter, can an Android Pro license key unlock desktop too (same
  Stripe/D1 backend, `pro/website/functions/api/validate.js` already just
  checks a key against the database — no reason it couldn't validate from a
  second client), or is desktop a separate purchase?

**Default to unrestricted (matching current `classydl web` behavior) unless
told otherwise** — don't add a paywall to a previously-free tool without
explicit sign-off; that's a monetization/trust decision, not something to
infer.

### 6. Tests

Add `tests/test_desktop_web_entry.py` (skip cleanly if `tkinter` isn't
importable, same pattern as `tests/test_easy_ui.py` / `test_cli_compat.py` —
see `CLAUDE.md`'s testing section for why that skip exists in this sandboxed
dev environment). Cover, with `webbrowser.open` and the actual server start
mocked out:
- Password is generated once and reused on a second "launch" (same data dir).
- The URL passed to `webbrowser.open` contains `?autologin=<the password>`.
- A bind failure (port already in use) doesn't crash — falls back to opening
  the browser to the existing instance.

For the `static/index.html` auto-login change, extend the existing
Playwright-based manual verification approach used elsewhere in this
project's history (see how the license-popup and settings-overflow fixes were
verified in earlier session work: spin up the real
`video_downloader.web.server.create_server(...)` on a background thread,
drive it with Playwright) — specifically verify: loading
`/?autologin=<password>` lands on the authenticated app view with no visible
login screen flash, and the URL no longer contains the password afterward.

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
