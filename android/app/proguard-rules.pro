# R8 configuration for DownloadThat.
#
# Chaquopy contributes its own rules automatically (the Gradle plugin extracts
# com/chaquo/python/proguard-rules.pro from its jar and calls proguardFile on
# it, keeping com.chaquo.python.** plus the kotlin.jvm.functions classes its
# Cython code reflects on) - don't duplicate those here.
#
# What DOES belong here is every Java/Kotlin member that only Python ever
# calls. Chaquopy resolves those by NAME at runtime, so R8 sees no caller,
# renames or removes them, and the call site then fails SILENTLY: jclass()
# raises inside a broad `except Exception` in android_bridge.py, and
# android_entry._notify_server_ready() does
# getattr(notifier, "onServerReady", None) and simply skips a missing
# callback. Nothing in logcat or the emulator matrix says "you shrank away the
# app's startup callback", so every rule below is load-bearing.

# Keep Play Console crash reports mappable to real line numbers.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ServerRuntime.RuntimeBridge is handed to android_entry.start() as `notifier`;
# Python calls onServerReady() / onJobsChanged(json) on it by name. Rename
# onServerReady and the runtime never leaves STARTING - the WebView never
# loads and no download notification ever updates.
-keep class de.classydl.app.ServerRuntime$RuntimeBridge { *; }

# Passed to media_search.start_search_session_json() as `cancellation_signal`;
# Python probes it with getattr(..., "isCancelled").
-keep class de.classydl.app.SearchActivity$SearchCancellationSignal { *; }

# android_bridge.open_file() resolves this via jclass() to build the
# PLAY_INTERNAL intent. The manifest entry already pins the name; this states
# the Python-side dependency explicitly so it survives a manifest refactor.
-keep class de.classydl.app.PlayerActivity

# Reached ONLY from Python (android_bridge.open_file / export_file), so R8 has
# no Java caller to trace: FileProvider.getUriForFile() and the DocumentFile
# tree API would otherwise be renamed, or dropped from the build outright.
-keep class androidx.core.content.FileProvider { *; }
-keep class androidx.documentfile.provider.** { *; }

# window.AndroidBridge in web/static/index.html - the WebView calls these by
# name from JavaScript. AGP's default file carries this rule too; kept
# explicit because losing it silently disables every native control in the
# web UI (folder picker, player handoff, purchase flow).
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Guava arrives transitively via media3-common (ListenableFuture) and refers to
# compile-only annotation / static-analysis packages that don't exist at
# runtime. R8 full mode - the AGP 8 default - reports such references as
# missing-class errors unless they're declared expected. None of these are
# needed on-device.
-dontwarn com.google.errorprone.annotations.**
-dontwarn com.google.j2objc.annotations.**
-dontwarn javax.annotation.**
-dontwarn org.checkerframework.**
