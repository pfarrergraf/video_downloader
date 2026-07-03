# ffmpeg subprocess → JNI migration — architecture research & go/no-go

Produced by a Claude Opus 4.8 planning agent on 2026-07-03, at the maintainer's
request, after Google Play Protect flagged a sideloaded update of the app as
"Diese App ist eine Fälschung" (fake app). This is a planning document only —
no code from this investigation has been implemented. See
`docs/ANDROID_APP_PLAN.md` Phase 7 for the (separate, in-progress) Play
Console registration work, which is the primary fix being pursued for the
Play Protect flag.

**Branch:** `claude/ffmpeg-jni-investigation` (planning only, no code changes)

---

## TL;DR / recommendation

**Recommend against a full JNI/native-library rewrite of ffmpeg as the fix for
the Play Protect flag, and against it as a near-term priority at all.** The
evidence points to the Play Protect "Fälschung" flag being driven
overwhelmingly by *publisher/signing-identity* signals (self-signed key from
an unregistered developer, triggered on an in-place update), not by the
"disguised-`.so` subprocess" technique. That is exactly what the
already-in-progress Play Console registration + Play App Signing work on the
other branch addresses. Many Play-Store-approved apps ship and `exec()`
bundled binaries via this identical `jniLibs`/`nativeLibraryDir` mechanism,
and Google's own Device-and-Network-Abuse policy explicitly permits executing
code that ships *inside* the APK (it forbids only *fetching* executable code
from outside Play). Meanwhile the JNI rewrite carries large, ongoing costs
and one genuinely serious reliability hazard (ffmpeg's `main()` is not
designed to be called repeatedly in a long-lived process — which is
precisely this app's architecture).

So: **do the developer-registration fix first, confirm whether the flag
clears, and only then consider the JNI work — as optional defense-in-depth,
not as the required remedy.** The rest of this document (a) lays out that
reasoning with the evidence, (b) defines what "genuine JNI" actually and
unavoidably means here given yt-dlp's constraints, and (c) gives a complete,
phased, file-by-file implementation + fallback plan for *if you choose to
proceed anyway*, structured so it can never regress the proven subprocess
path.

---

## Part 1 — Should we actually do this?

### 1.1 What actually triggered the flag (the evidence)

The specific message ("Diese App ist eine Fälschung" / this app is a fake),
the fact that it blocked an **update** but a **fresh install** worked, and
that it comes from Play Protect's on-device real-time scanner, all line up
with Play Protect's **developer-recognition / signing-identity** heuristic
rather than a code-technique heuristic:

- Google's own user-facing description of the relevant warning is literally
  *"Play Protect doesn't recognize this app's developer. Apps from unknown
  developers can sometimes be unsafe."* ([Play Protect user
  help](https://support.google.com/googleplay/answer/2812853), [Cafebazaar:
  Blocked by Play
  Protect](https://developers.cafebazaar.ir/en/app-publish-guidelines/academy/blocked-play-protect)).
- Play Protect *"provides additional validation by checking that app updates
  are signed with your upgraded key"* and flags apps where the signing
  identity isn't recognized/registered ([Use Play App
  Signing](https://support.google.com/googleplay/android-developer/answer/9842756)).
  An in-place update from a self-signed key belonging to no known developer
  is a textbook trigger; the "update blocked, fresh install fine" asymmetry
  is characteristic of the update-signature/publisher-reputation path, not of
  static code scanning (which would block both equally).
- Google's developer guidance for resolving Play Protect warnings is
  entirely about *policy compliance, minimal permissions, no remote code, and
  an appeal path* — it does **not** tell developers to stop bundling native
  executables ([Developer Guidance for Play Protect
  Warnings](https://developers.google.com/android/play-protect/warning-dev-guidance)).

Registering as a Play Console developer and enrolling in **Play App
Signing** establishes exactly the trusted signing identity this heuristic
keys on. That work (on `claude/gothic-downloader-website-bp7r2u`) is the
correctly-targeted fix, and it addresses the flag "regardless of the ffmpeg
technique," as the maintainer already surmised and as
`docs/ANDROID_APP_PLAN.md` Phase 7 records.

### 1.2 Is the "disguised-`.so` + subprocess" technique actually a policy or heuristic problem?

Researching this specifically, the answer is **no, not on its own**:

- **It's a widely-used, documented, standard workaround.** The "rename the
  executable to `libXXX.so` and drop it in `jniLibs/` so the installer
  extracts it into `nativeLibraryDir` with the execute bit" pattern is
  described across the ecosystem as *the* way to ship a runnable binary in an
  Android app ([bravobit/FFmpeg-Android PR #130 using jniLibs for targetSdk
  29](https://github.com/bravobit/FFmpeg-Android/pull/130); [ProAndroidDev: A
  Story about FFmpeg on Android, Part
  II](https://proandroiddev.com/a-story-about-ffmpeg-in-android-part-ii-integration-55fb217251f0)).
  Play-approved apps ship bundled binaries this way routinely.
- **Google Play's Device-and-Network-Abuse / dynamic-code policy targets
  *remote* code, not *bundled* code.** The prohibition is on apps that
  "download executable code (such as dex files or native code) from a source
  other than Google Play." Loading/executing code that is *already packaged
  in the installation package* is explicitly legitimate ([Oversecured: Why
  dynamic code loading could be
  dangerous](https://blog.oversecured.com/Why-dynamic-code-loading-could-be-dangerous-for-your-apps-a-Google-example/);
  [DYDROID, CMU](https://www.cs.cmu.edu/~rdriley/research/pubs/dydroid.pdf)).
  This app ships ffmpeg inside the APK and fetches nothing at runtime — it is
  on the compliant side of that line, and a JNI rewrite does not change that
  (both bundle the same code).
- **The exec you do is from the *blessed* location.** Android 10+ enforces
  W^X: `targetSdk ≥ 29` apps cannot `exec()` files from their *writable*
  storage (this is why Termux had to stop updating on Play and now relies on
  a policy-violating `system_linker_exec` hack — but note *Termux's* problem
  is that it execs files in its writable `$HOME`, which is a fundamentally
  different situation) ([Termux and Android 10
  wiki](https://github.com/termux/termux-packages/wiki/Termux-and-Android-10/5d899145ab70caa6e484609baf6c354651150230);
  [Termux W^X issue #2155](https://github.com/termux/termux-app/issues/2155);
  [Termux Play Store discussion
  #4000](https://github.com/termux/termux-app/discussions/4000)). **This app
  execs only from `nativeLibraryDir`, a read-only, installer-populated
  directory — the sanctioned path that is *not* affected by W^X.** So the
  app is already doing the "correct" version of the trick.
- **No documented precedent of "switch subprocess-ffmpeg → JNI-ffmpeg to
  clear a Play Protect flag."** This was searched for specifically; none
  found. The prominent JNI ffmpeg library (`ffmpeg-kit`, successor to
  `mobile-ffmpeg`) was **retired in January 2025 with its binaries pulled**
  ([ffmpeg-kit repo](https://github.com/arthenica/ffmpeg-kit); [It Path
  Solutions: No More
  FFmpegKit](https://www.itpathsolutions.com/ffmpegkit-shutdown-what-to-do-next))
  — i.e. the ecosystem is moving *away* from maintained JNI-ffmpeg, not
  toward it, and none of the migration guidance frames JNI-vs-subprocess as a
  Play Protect matter.

### 1.3 Would "genuine JNI" even change this app's heuristic profile?

Only marginally, and not in the dimension that flagged it:

- **Static scanner view:** either way the APK contains the same ~20+ MB of
  ffmpeg native code. What a genuine `.so` *removes* is the specific artifact
  of "an ELF **executable** (a `-pie`, statically-linked program with an
  entry point and no JNI exports) masquerading as a shared library under
  `lib/`." A scanner *can* tell an executable from a real library, so this is
  a small, real reduction in "looks like a dropped binary" surface — plus it
  removes any runtime `fork`/`exec` syscalls a behavioral sandbox might
  notice, and the `LD_LIBRARY_PATH`+exec dance. These are hygiene wins.
- **But** bundling ffmpeg as a *real* `.so` doesn't make the 20 MB of native
  code smaller or less "suspicious" by size; if anything a large opaque
  native blob is its own (weak) heuristic input either way. And crucially,
  none of this touches the **publisher-identity** signal that actually fired
  here.

**Bottom line for Part 1:** The JNI rewrite is at best a minor
defense-in-depth improvement to a signal that is probably not what's
flagging you, at the cost of substantial engineering and a real reliability
hazard (§2.5). The high-leverage fix is developer registration + Play App
Signing. **Recommendation: ship that, verify the flag clears, and treat
JNI-ffmpeg as optional.** If, after registration, the flag persists *and*
you can attribute it to the ffmpeg blob, revisit Part 3 of this doc.

---

## Part 2 — If we proceed anyway: what "genuine JNI" concretely means here

The hard constraint dominates everything: **yt-dlp only knows how to run
ffmpeg as a subprocess given an argv and a binary path.** There is no libav
API binding inside yt-dlp and no plugin seam for one. The exact shape of the
chokepoint is in yt-dlp's source
([yt_dlp/postprocessor/ffmpeg.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/postprocessor/ffmpeg.py)):

- `FFmpegPostProcessor.real_run_ffmpeg()` is the single method that builds
  the full command array and calls `Popen.run(...)`. Every subclass
  (`FFmpegExtractAudioPP`, `FFmpegMergerPP`, `FFmpegEmbedSubtitlePP`,
  `FFmpegVideoRemuxerPP`, the `FFmpegFixup*PP` family, etc.) routes through
  `run_ffmpeg` → `run_ffmpeg_multiple_files` → `real_run_ffmpeg`.
- Two more subprocess sites exist: `get_audio_codec()` and
  `get_metadata_object()`, which shell out to **ffprobe** (a *separate*
  binary — note the current build ships only `ffmpeg`, not `ffprobe`, so
  these already degrade gracefully today).
- Path resolution: `_determine_executables()` reads `ffmpeg_location` (the
  option this app sets) and `self.executable` returns the resolved path.

This has a decisive consequence:

> **Any in-process replacement must still accept an ffmpeg-CLI argv and
> behave like the ffmpeg CLI.** You are not going to feed yt-dlp a libav API.
> Therefore "genuine JNI" here does **not** mean "rewrite merging/extraction
> against libavformat/libavcodec." It means "run ffmpeg's own CLI
> `main(argc, argv)` in-process, loaded as a real shared library, instead of
> `fork`/`exec`ing it." This is precisely the architecture ffmpeg-kit used —
> and note even ffmpeg-kit's "JNI" layer "still basically executes FFmpeg in
> command-line style" ([Deemaze: Building the archived
> FFmpegKit](https://medium.com/deemaze-software/android-building-the-archived-ffmpegkit-878db187cc2c)).

### Option A — Monkeypatch/subclass yt-dlp's `FFmpegPostProcessor.real_run_ffmpeg`

**What it means:** At Android startup, install our own postprocessor base
(or monkeypatch `real_run_ffmpeg`) that, instead of `Popen`, builds the same
argv and dispatches it to an in-process ffmpeg (via Option C's native lib,
below). Fall back to the original method if anything about the patch doesn't
fit.

- **Invasiveness:** Small *code* surface (one method), but semantically
  fragile. `real_run_ffmpeg` handles stdin/`-progress`/stderr streaming,
  timeouts, `-y`/overwrite, and error parsing; a faithful replacement must
  reproduce its stdout/stderr/returncode contract or yt-dlp's error handling
  breaks.
- **Version durability:** This is the weak point. The project upgrades
  yt-dlp regularly for extractor fixes (`yt-dlp>=2024.12.13`).
  `real_run_ffmpeg`'s internals *do* change across releases. Mitigation: pin
  the override to the smallest possible surface, add a startup self-check
  that verifies the method exists with the expected signature, and **fail
  safe to the stock subprocess implementation** whenever the check fails or
  the native call errors. (On Android the "subprocess fallback" is the
  existing `nativeLibraryDir/libffmpeg.so` exec — so "fallback" here really
  means "keep today's working behavior.")
- **Verdict:** This is the *only* viable Python-side seam, and it must be
  paired with a native in-process ffmpeg (Option C). It is not itself "JNI";
  it's the glue.

### Option B — PyAV / a custom libav* Python binding via Chaquopy

**What it means:** Cross-compile ffmpeg's libraries + PyAV (Cython) for each
Android ABI, ship as a Chaquopy wheel, and re-implement merge/extract/remux
against the libav API.

- **Chaquopy native-extension reality:** Chaquopy can only install native
  packages it has **pre-built in its own repo**, or wheels **you** build with
  its `build-wheel` tooling (a `meta.yaml` recipe + `build.sh`, Docker-based,
  Linux-x86-64 only), then reference via `pip { options
  "--extra-index-url", <dist> }` ([Chaquopy
  docs](https://chaquo.com/chaquopy/doc/current/android.html);
  [chaquopy/server/pypi README](https://github.com/chaquo/chaquopy/blob/master/server/pypi/README.md);
  [chaquo/chaquopy#120 "cannot compile native
  code"](https://github.com/chaquo/chaquopy/issues/120)). PyAV is **not** in
  Chaquopy's repo, so this is a full custom-wheel effort per ABI, on top of
  cross-compiling ffmpeg's shared libs.
- **The killer:** yt-dlp can't consume PyAV. You'd have to *reimplement*
  yt-dlp's postprocessing (stream merge, mp3 extraction, subtitle embed, the
  `Fixup*` passes) against libav — a large, correctness-sensitive rewrite
  that also has to stay compatible with what yt-dlp expects on disk
  afterward. And it only helps the yt-dlp path, not
  `FFmpegStrategy`/`conversion.py`.
- **Verdict:** **Reject.** Highest effort, highest correctness risk, doesn't
  satisfy the yt-dlp constraint, and duplicates functionality yt-dlp already
  gets right.

### Option C — Compile ffmpeg's CLI as a shared library exposing `ffmpeg_main(argv)`, call it in-process via a tiny JNI shim (recommended, *if* proceeding)

**What it means (the ffmpeg-kit architecture, self-built):** Change the
existing `build_ffmpeg_android.sh` so that instead of producing a standalone
`ffmpeg` executable, it links `fftools/ffmpeg.c` et al. into a real shared
library `libffmpegcli.so` with `main` renamed to an exported
`ffmpeg_execute(int argc, char** argv)` (ffmpeg's `fftools` are structured to
allow this; this is exactly what ffmpeg-kit did). Add a small Kotlin/Java
class with a `native` method bound to that `.so` via `System.loadLibrary`.
From Python, the patched `real_run_ffmpeg` (Option A) calls that method
through Chaquopy's `from java import jclass` bridge, passing the argv it
already built, and gets back an exit code + captured stderr.

- **Reuses the existing build** (Part 3), same ffmpeg version/codecs/16
  KB-alignment flags. It is a *real* `System.loadLibrary`-loaded `.so`, so it
  eliminates the executable-masquerading artifact and the fork/exec — the
  actual (modest) heuristic wins from §1.3.
- **ffprobe:** `get_audio_codec`/`get_metadata_object` would also need
  routing (or continue to degrade as today, since ffprobe isn't shipped
  now). Cleanest is to also expose `ffprobe_execute` from the same lib.
- **Verdict:** This is *the* concrete meaning of "genuine JNI" for this app,
  and the only option that both satisfies yt-dlp's constraint and delivers
  the heuristic benefit. It carries the §2.5 hazard below.

### Option D — Other approaches worth naming

- **Persistent helper subprocess instead of one-shot exec:** doesn't remove
  exec, so no heuristic benefit; strictly worse than status quo for this
  goal.
- **Avoid bundling ffmpeg for the common case (pure-Python remux):** The
  dominant use is merging DASH `bestvideo+bestaudio` into mp4 (the hard-won
  quality fix in `_video_format_selector`) and mp3 extraction. There is no
  robust pure-Python muxer for arbitrary codecs; yt-dlp itself requires
  ffmpeg for merges. You could *prefer pre-muxed progressive formats* to skip
  ffmpeg — but that is exactly the quality cap the project deliberately
  fought off (see `_video_format_selector`'s fallback comments in
  `video_downloader/strategies.py`). So this cannot be the default. **Reject
  as a primary strategy**, though the existing no-ffmpeg fallback should
  absolutely be *retained* as the last-resort safety net.

### 2.5 The serious reliability hazard with in-process ffmpeg (Option C)

This is the strongest *engineering* argument against proceeding, and it must
be stated plainly:

**ffmpeg's `main()` is not designed to be invoked repeatedly within one
long-lived process.** It uses process-global state, calls `exit()` on fatal
errors, and does not fully release memory between runs. This app is
*precisely* the worst case for that: `android_entry.start()` launches a
**persistent** Python web server with **`workers=2`** that will run **many**
downloads (and thus many ffmpeg invocations) over the app's lifetime,
potentially concurrently.

- A subprocess gives every ffmpeg run a **fresh, isolated address space**
  that's reclaimed on exit — which is exactly why running ffmpeg
  out-of-process is the *robust* design and why yt-dlp shells out. In-process
  `ffmpeg_execute` means: a stray `exit()` can kill the whole app; two
  concurrent workers can collide on ffmpeg's globals; and memory/handle leaks
  accumulate across a session. ffmpeg-kit had to invest heavily to tame this
  and it was still a known pain — and it's now unmaintained.
- Mitigations exist (serialize ffmpeg calls behind a lock, intercept
  `exit()`, reset state) but they add complexity and never fully match
  subprocess isolation.

So the JNI approach trades a *tiny* heuristic improvement for a *real*
robustness regression risk in exactly the "the app can't download
good-quality video" area the project has already had to fix once. This
substantially reinforces the Part 1 recommendation.

---

## Part 3 — Concrete migration plan (only if proceeding with Option C + A)

Design principle throughout: **the non-Android paths (CLI/TUI/desktop-UI/web-UI
on Termux) must be byte-for-byte unaffected** — they resolve a real system
`ffmpeg` on `PATH` and must keep doing so. All new behavior is gated to
"running under Chaquopy," detected the same way existing code already does
it (`try: from java import ... except ImportError`). And **the current
subprocess path stays intact as the fallback** (Part 4).

### Phase 0 — Decision gate (do this first, before any code)
Complete developer registration + Play App Signing (other branch),
publish/update through the testing track, and **observe whether the Play
Protect flag clears.** If it does, stop — file this doc as "evaluated, not
needed." Only proceed if the flag persists and is attributable to the ffmpeg
blob.

### Phase 1 — Build ffmpeg as a shared library (`.github/scripts/build_ffmpeg_android.sh`)
- Add a build variant that compiles ffmpeg's `fftools` (`ffmpeg.c`,
  `cmdutils.c`, `ffmpeg_opt.c`, etc.) into `libffmpegcli.so` with
  `main`→`ffmpeg_execute` (and optionally `ffprobe.c`→`ffprobe_execute`),
  instead of / in addition to the standalone binary. Keep
  `--enable-libmp3lame`, the NDK LLVM toolchain, and the
  `-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384` 16 KB-alignment
  flags. Drop `-pie` (that's for executables); produce a genuine `-shared`
  library exporting the two entrypoints.
- Add a tiny JNI wrapper C file (`extern "C" JNIEXPORT jint JNICALL
  Java_de_classydl_app_FfmpegNative_execute(...)`) that marshals a Java
  `String[]` into `argv`, calls `ffmpeg_execute`, and returns the exit code;
  capture stderr via a pipe or an ffmpeg log callback. Compile it into the
  same `.so` (or a thin companion lib linked against it).
- **Effort/risk:** this is where most of the pain lives — `fftools` linking,
  stderr capture, and 16 KB alignment on a `-shared` build. Budget for
  several CI iterations (the project's own history: a comparable ffmpeg
  packaging change took "5 iterations to get green").

### Phase 2 — Android glue
- **`android/app/src/main/java/de/classydl/app/`**: add `FfmpegNative.kt`
  (or `.java`) with `System.loadLibrary("ffmpegcli")` in a
  `companion object`/static block and `external fun execute(args:
  Array<String>): Int` (+ a way to retrieve captured stderr, e.g. return a
  small result object or expose a `lastStderr()`).
- **`MainActivity.kt` `resolveFfmpegBinary()`:** keep it. It should now
  *also* report whether the native lib is available, but the simplest,
  safest shape is: leave `resolveFfmpegBinary()` returning the
  `nativeLibraryDir/libffmpeg.so` path as today (subprocess fallback stays
  wired), and add a *separate* signal (e.g. an extra boolean/string arg to
  `android_entry.start`) telling Python "an in-process ffmpeg JNI entrypoint
  is available." Do **not** remove the disguised-`.so` binary yet — it's the
  fallback for Phase 4.
- **`android/app/build.gradle`:** `libffmpegcli.so` is now a *real* JNI
  library, so it can live under `jniLibs/<abi>/` with the **modern**
  packaging (mmap'd, not extracted) — but note `useLegacyPackaging = true` is
  currently forced *for the disguised executable*. If both coexist during
  migration, keep legacy packaging (harmless for the real lib). Once the
  executable is retired, `useLegacyPackaging` can revert to default and that
  whole comment block in `build.gradle` goes away — a genuine cleanup win.

### Phase 3 — Python seam (`video_downloader/strategies.py` + a new small module)
- Add a new module, e.g. `video_downloader/ffmpeg_runtime.py`, that exposes a
  single function `run_ffmpeg_argv(argv) -> (returncode, stderr)` with two
  implementations chosen at import/first-call time:
  1. **Android/Chaquopy in-process:** `from java import jclass; FfmpegNative
     = jclass("de.classydl.app.FfmpegNative"); ...` — gated by `try/except
     ImportError` exactly like `android_entry._publish_file_to_downloads`.
  2. **Everything else / fallback:** `subprocess.run(argv, ...)` — identical
     to today.
- **`YtDlpStrategy.download`:** at the top, when running under Chaquopy *and*
  the JNI entrypoint is available, install the yt-dlp override (Option A):
  subclass/patch so `real_run_ffmpeg` routes its argv through
  `ffmpeg_runtime.run_ffmpeg_argv`. Wrap the patch install in the startup
  self-check; on any failure, leave yt-dlp stock (it then uses
  `ffmpeg_location` → the still-present disguised `.so`). Keep
  `ydl_opts["ffmpeg_location"]` set regardless, so the fallback works.
- **`FFmpegStrategy.download`:** replace the direct `subprocess.run([request.ffmpeg_binary,
  ...])` with `ffmpeg_runtime.run_ffmpeg_argv([...])`. Note
  `shutil.which(request.ffmpeg_binary)` must be made tolerant of "no binary
  on PATH but JNI available" — currently it hard-fails if the binary isn't
  found; add an "or JNI available" condition.
- **`conversion.py`** (`run_ffmpeg_mp4_conversion`, used by `cli.py` and
  `scripts/convert_to_mp4.py`, i.e. desktop/CLI) is a *third* subprocess
  site. It can route through the same `ffmpeg_runtime` shim for consistency,
  but since it's non-Android it will simply use the subprocess
  implementation — no behavior change. Leaving it as-is is also acceptable
  for scope control.
- **Non-Android guarantee:** because implementation (2) is byte-identical to
  current `subprocess.run`, and (1) is only ever selected when `from java
  import` succeeds, CLI/TUI/desktop/web-on-Termux are provably unaffected.
  Add/keep unit tests asserting the shim picks subprocess off-Android.

### Phase 4 — Concurrency & lifecycle hardening (mandatory given §2.5)
- Serialize all `run_ffmpeg_argv` in-process calls behind a global lock (the
  server runs `workers=2`) to avoid ffmpeg-global-state collisions.
- Intercept/neutralize `exit()` in the native shim so an ffmpeg fatal error
  returns a code instead of killing the app.
- Add a "safety valve": on any in-process ffmpeg crash/nonzero-with-no-output,
  **automatically fall back** to the subprocess path (disguised `.so` still
  present) for that one job, and log it. This makes the JNI path strictly
  additive.

### Phase 5 — CI (there is no dev device/emulator; follow the established CI-only pattern per `docs/ANDROID_APP_PLAN.md`)
- **`android-build.yml`** and **`android-release.yml`**: the `build-ffmpeg`
  job now also (or instead) builds `libffmpegcli.so` per ABI; the "Place
  ffmpeg binaries into jniLibs" step places the real lib (and, during
  migration, still the disguised executable).
- Extend **`ffmpeg_exec_test.sh`** with a companion that loads the lib and
  calls `ffmpeg_execute(["-version"])` from within a tiny on-device harness
  (or via the app), proving the in-process path runs on-device — analogous to
  how the current script proves the standalone binary runs.
- Extend **`download_pipeline_test.sh`** to run a real merge/mp3 job through
  the JNI path and confirm the output file, and separately a *second* job in
  the same app session to catch in-process state-leak regressions (the §2.5
  hazard).
- **Effort estimate:** realistically **5+ CI iterations** to green given the
  `fftools`-as-`.so` linking, stderr capture, 16 KB alignment on a shared
  build, and the yt-dlp override contract — consistent with the project's own
  "5 iterations" precedent for ffmpeg packaging changes. Non-trivial; plan
  for a multi-session effort.

---

## Part 4 — Fallback / rollback plan

Because this is an experimental branch and the "good-quality video download"
case was a hard-won fix (`_video_format_selector`), the migration must be
**strictly additive and instantly reversible**:

1. **Keep the disguised `libffmpeg.so` executable shipping the whole time.**
   Do not remove it or flip `useLegacyPackaging` until the JNI path has been
   green in CI across multiple releases *and* validated on a real device.
   `resolveFfmpegBinary()` and `ffmpeg_location` stay wired to it. The JNI
   lib ships *alongside* it.
2. **Runtime feature flag / auto-fallback.** The Python shim selects JNI
   only when (a) running under Chaquopy, (b) the native entrypoint loaded,
   and (c) a startup self-check of the yt-dlp override passed. Any failure →
   stock subprocess behavior. Add a persisted setting (via the existing
   `QueueStore.set_setting`/`get_setting`) so the JNI path can be
   force-disabled without a rebuild if a field issue appears.
3. **Per-job safety valve** (Phase 4): if an in-process ffmpeg run fails
   abnormally, retry that job via subprocess automatically.
4. **Branch-level rollback:** the entire change is isolated on
   `claude/ffmpeg-jni-investigation`; abandoning it costs nothing since the
   shipping release path is the other branch. Keep the JNI work behind the
   flag even after merge, defaulted **off**, until proven.
5. **Retention of the no-ffmpeg fallback:** leave `_audio_format_selector`/
   `_video_format_selector`'s "no ffmpeg available" branches untouched — they
   remain the ultimate backstop so the app "can always download *something*"
   (the exact invariant those comments protect).

---

## Honest closing assessment

- **Primary path:** Play Console registration + Play App Signing (other
  branch) is the correctly-targeted, high-leverage fix for the "Fälschung"
  flag. Do it, confirm, likely done.
- **JNI rewrite:** technically feasible only in the Option C + A shape
  (in-process ffmpeg-CLI `main()` via a real `.so`, glued through a
  monkeypatched `real_run_ffmpeg`). It delivers a *minor* heuristic-hygiene
  benefit to a signal that probably isn't what flagged you, at the cost of a
  genuine reliability hazard (§2.5: ffmpeg `main()` in a long-lived
  multi-worker process) and ongoing maintenance against yt-dlp upgrades and
  an ecosystem that has *abandoned* maintained JNI-ffmpeg (ffmpeg-kit
  retired). **Recommend deferring it; pursue only as flag-persistent-after-registration
  defense-in-depth, strictly behind the additive/fallback design in Parts
  3–4.**

### Sources
- [Developer Guidance for Google Play Protect Warnings](https://developers.google.com/android/play-protect/warning-dev-guidance)
- [Use Google Play Protect (user help)](https://support.google.com/googleplay/answer/2812853) · [Use Play App Signing](https://support.google.com/googleplay/android-developer/answer/9842756) · [Device and Network Abuse policy](https://support.google.com/googleplay/android-developer/answer/16559646) · [Blocked by Play Protect (Cafebazaar)](https://developers.cafebazaar.ir/en/app-publish-guidelines/academy/blocked-play-protect)
- [Oversecured: dynamic code loading dangers](https://blog.oversecured.com/Why-dynamic-code-loading-could-be-dangerous-for-your-apps-a-Google-example/) · [DYDROID (CMU)](https://www.cs.cmu.edu/~rdriley/research/pubs/dydroid.pdf)
- [bravobit/FFmpeg-Android PR #130 (jniLibs, targetSdk 29)](https://github.com/bravobit/FFmpeg-Android/pull/130) · [ProAndroidDev: FFmpeg on Android Part II](https://proandroiddev.com/a-story-about-ffmpeg-in-android-part-ii-integration-55fb217251f0)
- [Termux and Android 10 wiki](https://github.com/termux/termux-packages/wiki/Termux-and-Android-10/5d899145ab70caa6e484609baf6c354651150230) · [Termux W^X issue #2155](https://github.com/termux/termux-app/issues/2155) · [Termux Play Store discussion #4000](https://github.com/termux/termux-app/discussions/4000)
- [yt-dlp postprocessor/ffmpeg.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/postprocessor/ffmpeg.py) · [yt-dlp post-processing pipeline (DeepWiki)](https://deepwiki.com/yt-dlp/yt-dlp/2.5-post-processing-pipeline)
- [ffmpeg-kit (retired)](https://github.com/arthenica/ffmpeg-kit) · [mobile-ffmpeg (unmaintained)](https://github.com/tanersener/mobile-ffmpeg) · [It Path Solutions: No More FFmpegKit](https://www.itpathsolutions.com/ffmpegkit-shutdown-what-to-do-next) · [Deemaze: Building the archived FFmpegKit](https://medium.com/deemaze-software/android-building-the-archived-ffmpegkit-878db187cc2c)
- [Chaquopy Gradle plugin docs](https://chaquo.com/chaquopy/doc/current/android.html) · [chaquopy/server/pypi README (custom wheels)](https://github.com/chaquo/chaquopy/blob/master/server/pypi/README.md) · [chaquo/chaquopy#120 (cannot compile native code)](https://github.com/chaquo/chaquopy/issues/120)

### Critical files referenced
- `video_downloader/strategies.py`
- `.github/scripts/build_ffmpeg_android.sh`
- `android/app/src/main/java/de/classydl/app/MainActivity.kt`
- `android/app/build.gradle`
- `.github/workflows/android-build.yml` and `.github/workflows/android-release.yml`
- Also touched in a real implementation: `video_downloader/android_entry.py`
  (availability signal), a new `video_downloader/ffmpeg_runtime.py` shim, and
  optionally `video_downloader/conversion.py` (third subprocess site).
