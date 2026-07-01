# Project Memory

A running log of decisions and incidents worth remembering, in case future work
(by Claude or a human) needs the "why," not just the "what." Newest entries on top.

## 2026-07-01 — Gothic web UI, Termux deployment, two debugging rounds

**Goal:** let ClassyDL be driven from a phone via a browser, initially explored as a
hosted web app, then narrowed to "must run with no external server — entirely on the
phone itself" once the user clarified they didn't want to wait for hosting setup and
had already had a bad experience trying to package it as a native app.

**Decision — Termux, not a native app rewrite.** Android + Termux can run a real
Python/ffmpeg environment on-device, so the existing scraper/queue/download code could
be reused unchanged behind a small local web server, opened at `127.0.0.1` in the
phone's own browser. No APK build, no app store, no separate server host.

**Incident 1 — `pip install --upgrade pip` blocked by Termux.**
First version of `scripts/termux_setup.sh` ran `pip install --upgrade pip` before
installing the project. Termux ships a patched pip that refuses to self-upgrade
("Installing pip is forbidden, this will break the python-pip package (termux)"),
and printed the error and exited non-zero. Because the script had `set -e`, it
aborted right there — `pip install ".[web]"` never ran — but `termux_run.sh` was
tried anyway afterward and failed with `classydl: command not found`, since nothing
had actually been installed.
**Fix:** deleted the `pip install --upgrade pip` line entirely. Termux manages pip
version via `pkg`, not pip itself.

**Incident 2 — `pydantic-core` has no Termux/Android wheel.**
The web backend was originally FastAPI + uvicorn. FastAPI depends on Pydantic v2,
whose validation core (`pydantic-core`) is a Rust extension. PyPI has no prebuilt
wheel for Termux's platform tag, so pip fell back to building it from source, which
requires a Rust toolchain Termux doesn't ship by default, and even with one, compiling
a Rust crate on a phone CPU is slow — it hung visibly for 6+ minutes with no output
change ("Installing build dependencies ... -").
**Fix:** rewrote `video_downloader/web/server.py` from a FastAPI app to a pure
standard-library implementation (`http.server.ThreadingHTTPServer` + a custom
`BaseHTTPRequestHandler`). Same routes, same cookie-session auth, same static file
serving — just no compiled dependencies anywhere in the chain. Removed
`fastapi`/`uvicorn`/`pydantic`/`starlette`/`httpx` from `pyproject.toml` entirely.
Tests were rewritten to hit the server over real HTTP instead of using FastAPI's
`TestClient`.

**Outcome:** confirmed working end-to-end on the user's Android phone via Termux
after both fixes — `bash scripts/termux_setup.sh && bash scripts/termux_run.sh`,
then `http://127.0.0.1:8420` in Chrome.

**Standing principle for this repo:** don't add a dependency with compiled/Rust/C
extensions (especially anywhere reachable from `classydl web`) without checking it
has real Termux/Android wheel coverage — "runs on a phone with no server" is a load-
bearing requirement here, not a nice-to-have.

## 2026-07-01 — Why the web UI exists at all

User wanted to use the downloader "via phone or any device with internet access."
Explored a Gothic-themed hosted web app first (FastAPI backend + static frontend,
deployable via Docker/VPS/Cloudflare) — that version still exists as an option
(`Dockerfile`, `--host 0.0.0.0` binding) for whoever wants a shared/remote deployment
later. The user then pivoted to wanting zero external hosting, landing on the
Termux/on-device approach above as the immediate priority.
