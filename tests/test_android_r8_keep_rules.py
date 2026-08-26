"""R8 is only safe here as long as every Python-reflected Java member is kept.

Chaquopy resolves Java classes and methods by name at runtime, so R8 sees no
caller and is free to rename or drop them. Both call sites swallow the result
(jclass() raises inside a broad `except Exception`, and the notifier callbacks
go through getattr(..., None)), so a missing keep rule ships as silently
broken behaviour rather than a crash. These tests fail instead.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "android" / "app" / "build.gradle"
RULES = ROOT / "android" / "app" / "proguard-rules.pro"
BRIDGE = ROOT / "video_downloader" / "android_bridge.py"
ENTRY = ROOT / "video_downloader" / "android_entry.py"
SEARCH = ROOT / "video_downloader" / "media_search.py"
KOTLIN = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app"

# Framework and Chaquopy runtime classes are never minified by this app's R8
# run: android.*/java.* come from the platform, com.chaquo.* is kept by the
# rules the Chaquopy Gradle plugin contributes itself.
PLATFORM_PREFIXES = ("android.", "androidx.annotation.", "java.", "javax.", "com.chaquo.")


def _kept_class_prefixes() -> list[str]:
    """Class patterns from plain `-keep class` rules, wildcards trimmed.

    Deliberately ignores -keepclassmembers: its `class *` pattern would match
    everything and make the coverage check below vacuous.
    """
    prefixes = []
    for line in RULES.read_text(encoding="utf-8").splitlines():
        match = re.match(r"-keep\s+class\s+([\w.$*]+)", line.strip())
        if match:
            prefix = match.group(1).replace("*", "")
            if prefix:
                prefixes.append(prefix)
    return prefixes


def test_release_and_debug_both_run_r8() -> None:
    text = GRADLE.read_text(encoding="utf-8")
    # Debug is minified too: the emulator matrix only ever installs the debug
    # APK, so release-only minification would ship untested keep rules.
    assert text.count("minifyEnabled true") == 2
    assert "minifyEnabled false" not in text
    assert text.count("'proguard-rules.pro'") == 2
    assert text.count("shrinkResources true") == 2


def test_python_reflected_classes_have_keep_rules() -> None:
    kept = _kept_class_prefixes()
    missing = set()
    for source in (BRIDGE, ENTRY):
        for name in re.findall(r'jclass\("([^"]+)"\)', source.read_text(encoding="utf-8")):
            base = name.split("$")[0]
            if base.startswith(PLATFORM_PREFIXES):
                continue
            if not any(base.startswith(prefix) for prefix in kept):
                missing.add(name)
    assert not missing, f"jclass() targets without a -keep rule in proguard-rules.pro: {sorted(missing)}"


def test_python_called_java_callbacks_are_kept() -> None:
    rules = RULES.read_text(encoding="utf-8")

    # android_entry.start() receives ServerRuntime.RuntimeBridge as `notifier`
    # and calls these by name; a renamed onServerReady leaves the runtime
    # stuck in STARTING forever.
    entry = ENTRY.read_text(encoding="utf-8")
    server_runtime = (KOTLIN / "ServerRuntime.kt").read_text(encoding="utf-8")
    assert 'getattr(notifier, "onServerReady"' in entry
    assert "notifier.onJobsChanged(" in entry
    assert "object RuntimeBridge" in server_runtime
    assert "-keep class de.classydl.app.ServerRuntime$RuntimeBridge { *; }" in rules

    # media_search.start_search_session_json() probes the Kotlin cancellation
    # signal the same way.
    search = SEARCH.read_text(encoding="utf-8")
    search_activity = (KOTLIN / "SearchActivity.kt").read_text(encoding="utf-8")
    assert 'getattr(cancellation_signal, "isCancelled"' in search
    assert "class SearchCancellationSignal" in search_activity
    assert "-keep class de.classydl.app.SearchActivity$SearchCancellationSignal { *; }" in rules


def test_webview_javascript_bridge_is_kept() -> None:
    rules = RULES.read_text(encoding="utf-8")
    main_activity = (KOTLIN / "MainActivity.kt").read_text(encoding="utf-8")
    assert "@JavascriptInterface" in main_activity
    assert "@android.webkit.JavascriptInterface <methods>;" in rules
