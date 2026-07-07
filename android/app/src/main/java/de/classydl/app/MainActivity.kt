package de.classydl.app

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.documentfile.provider.DocumentFile
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.security.SecureRandom

/**
 * Hosts the Gothic UI in a WebView, backed by the same Python web server used on
 * Termux — see video_downloader/android_entry.py for the Chaquopy entry point.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ClassyDL"
        private const val PORT = 8420
        private const val SERVER_URL = "http://127.0.0.1:$PORT"
        private const val MAX_LOAD_RETRIES = 20
        private const val PREFS_NAME = "classydl_prefs"
        private const val PREFS_PASSWORD_KEY = "server_password"
        // Fixed in debug builds so CI's download_pipeline_test.sh (and anyone
        // testing locally) can log in without needing to read it back out of
        // the app's SharedPreferences. Release builds (the ones actually
        // sideloaded onto other people's phones) always get a random
        // per-install password instead — see getOrCreatePassword().
        private const val DEBUG_PASSWORD = "classydl"

        // The license-check endpoint (pro/website/functions/api/validate.js)
        // is a Cloudflare Pages Function on the same deployment as the
        // marketing site/webhook, not a separate Worker - this used to point
        // at an unreplaced placeholder Worker subdomain, so
        // LicenseManager.refresh() always failed to resolve it and every
        // license key silently fell back to "invalid" (fails closed by
        // design - see licensing.py - which is why this went unnoticed
        // rather than erroring loudly).
        // Only wired up for release builds (see resolveLicenseApiBase()) so
        // CI's debug-build download_pipeline_test.sh — which never sets a
        // license key — keeps exercising the always-unrestricted path it
        // was written against, unaffected by free-tier limits.
        private const val LICENSE_API_BASE = "https://downloadthat.pages.dev"

        // Idempotency guard: Android may recreate the Activity (e.g. on a
        // config change) without restarting the process, causing onCreate →
        // startPythonServer() to run a second time. The second run_server()
        // call would fail to bind the already-occupied port 8420 (OSError:
        // [Errno 98] Address already in use) and crash that thread —
        // harmlessly for the app itself, but it also redundantly starts a
        // second _run_downloads_publisher thread, doubling SQLite polling.
        // @Volatile ensures the write is immediately visible to any thread
        // that reads it after onCreate returns.
        @Volatile private var serverStarted = false

        // First http(s) URL in a shared text - YouTube and most apps share
        // "Some title https://youtu.be/..." rather than a bare URL.
        private val SHARED_URL_REGEX = Regex("""https?://\S+""")

        private const val PREFS_LAST_CLIPBOARD_KEY = "last_clipboard_suggestion"
    }

    private var loadRetries = 0
    private lateinit var password: String
    private lateinit var webView: WebView
    private lateinit var folderPickerLauncher: ActivityResultLauncher<Uri?>

    // A URL shared into the app, waiting for the web UI to be ready.
    // @Volatile: written on the UI thread, read by the WebView's JS-bridge
    // thread (consumePendingSharedUrl).
    @Volatile private var pendingSharedUrl: String? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        password = getOrCreatePassword()
        startPythonServer()

        // Must be registered before STARTED (i.e. here in onCreate, not lazily
        // inside the bridge call) — ActivityResultRegistry throws otherwise.
        folderPickerLauncher = registerForActivityResult(
            ActivityResultContracts.OpenDocumentTree(),
        ) { uri -> onFolderPicked(uri) }

        handleShareIntent(intent)

        webView = findViewById(R.id.webview)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.addJavascriptInterface(WebAppBridge(), "AndroidBridge")
        applySystemFontScale()
        webView.webViewClient = object : WebViewClient() {
            // WebAppBridge is exposed to whatever page this WebView has loaded —
            // without this, following any link to a non-local page (e.g. one
            // reflected from a scraped site's content) would hand that page's
            // JavaScript the same native bridge (folder picker, etc.) that's
            // meant only for our own bundled UI. The WebView itself must never
            // navigate off 127.0.0.1, but legitimate outbound links (e.g. the
            // "Get Pro" button linking to the marketing site) still need to go
            // somewhere - hand those to the system browser instead of just
            // silently swallowing them.
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url ?: return true
                if (url.host == "127.0.0.1") return false
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                } catch (e: Exception) {
                    Log.e(TAG, "No app to handle $url", e)
                }
                return true
            }

            override fun onReceivedError(
                view: WebView?,
                errorCode: Int,
                description: String?,
                failingUrl: String?,
            ) {
                // The server thread may still be starting up when the first load
                // happens; retry with a short delay instead of showing a dead page.
                if (loadRetries < MAX_LOAD_RETRIES) {
                    loadRetries++
                    Handler(Looper.getMainLooper()).postDelayed({
                        view?.loadUrl(SERVER_URL)
                    }, 500)
                } else {
                    Log.e(TAG, "Giving up loading $failingUrl: $description")
                }
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // The server-side password gate exists to stop other apps on
                // the same device from hitting the loopback port, not to
                // challenge the user of this app — so log in automatically
                // instead of making them type a password they were never
                // shown. JSONObject.quote produces a safely escaped JS string
                // literal (belt-and-braces here since `password` is always
                // our own generated/fixed value, never external input).
                val quotedPassword = JSONObject.quote(password)
                view?.evaluateJavascript(
                    """
                    (function() {
                        var pw = document.getElementById('login-password');
                        var btn = document.getElementById('login-btn');
                        if (pw && btn) { pw.value = $quotedPassword; btn.click(); }
                    })();
                    """.trimIndent(),
                    null,
                )
            }
        }
        webView.loadUrl(SERVER_URL)
    }

    override fun onResume() {
        super.onResume()
        // The SAF folder picker (and any other system UI) pauses this Activity
        // while it's open — refresh the settings panel on return so a newly
        // picked folder's label shows up without the user reloading manually.
        webView.evaluateJavascript("window.refreshSettings && window.refreshSettings();", null)
    }

    // "Share -> DownloadThat" while the app is already running: singleTask
    // routes the new intent here instead of stacking a second Activity.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleShareIntent(intent)
        deliverSharedUrlToPage()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        // Android 10+ only lets the focused foreground app read the clipboard,
        // and onResume() fires *before* focus is granted - this is the
        // earliest callback where the read actually works.
        if (hasFocus) suggestClipboardUrl()
    }

    private fun handleShareIntent(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND || intent.type != "text/plain") return
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
        val url = SHARED_URL_REGEX.find(text)?.value ?: return
        pendingSharedUrl = url
        Log.i(TAG, "Received shared URL")
    }

    /**
     * Warm-path delivery of a shared URL into the already-loaded page. The JS
     * side reports whether window.onSharedUrl existed; only then is the
     * pending URL cleared — if the page wasn't ready yet, it stays pending
     * and the page pulls it itself via consumePendingSharedUrl() once its
     * auth flow completes (the cold-start path).
     */
    private fun deliverSharedUrlToPage() {
        val url = pendingSharedUrl ?: return
        if (!::webView.isInitialized) return
        val quoted = JSONObject.quote(url)
        webView.evaluateJavascript(
            "(function(){ if (window.onSharedUrl) { window.onSharedUrl($quoted); return true; } return false; })();",
        ) { result ->
            if (result == "true" && pendingSharedUrl == url) {
                pendingSharedUrl = null
            }
        }
    }

    /**
     * If the clipboard holds a link the user copied elsewhere, offer it as a
     * one-tap suggestion chip in the page (window.onClipboardUrl). Suggest
     * each distinct URL only once, ever — a suggestion that keeps coming
     * back after being dismissed is nagging, not helping.
     */
    private fun suggestClipboardUrl() {
        if (!::webView.isInitialized) return
        val clipboard = getSystemService(android.content.ClipboardManager::class.java) ?: return
        val clip = clipboard.primaryClip ?: return
        if (clip.itemCount == 0) return
        val text = clip.getItemAt(0).coerceToText(this)?.toString() ?: return
        val url = SHARED_URL_REGEX.find(text)?.value ?: return
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        if (prefs.getString(PREFS_LAST_CLIPBOARD_KEY, null) == url) return
        prefs.edit().putString(PREFS_LAST_CLIPBOARD_KEY, url).apply()
        val quoted = JSONObject.quote(url)
        webView.evaluateJavascript("window.onClipboardUrl && window.onClipboardUrl($quoted);", null)
    }

    /**
     * Make the WebView follow the system font-size setting (a core
     * accessibility need for the older half of the audience). Some WebView
     * builds already fold fontScale into the default textZoom — only apply
     * it when the default is still a plain 100, so it's never applied twice.
     * Capped at 200%: the page layout is verified to reflow without sideways
     * overflow up to there (see index.html's button wrapping rules).
     */
    private fun applySystemFontScale() {
        val scale = resources.configuration.fontScale
        if (webView.settings.textZoom == 100 && scale != 1.0f) {
            webView.settings.textZoom = (scale * 100).toInt().coerceIn(50, 200)
        }
    }

    private fun onFolderPicked(uri: Uri?) {
        if (uri == null) return
        contentResolver.takePersistableUriPermission(
            uri,
            Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
        )
        val label = DocumentFile.fromTreeUri(this, uri)?.name ?: uri.toString()
        Python.getInstance()
            .getModule("video_downloader.android_entry")
            .callAttr("set_export_folder", uri.toString(), label)
    }

    /** Exposed to the WebView as `window.AndroidBridge` — see static/index.html's settings panel. */
    private inner class WebAppBridge {
        @JavascriptInterface
        fun pickExportFolder() {
            runOnUiThread { folderPickerLauncher.launch(null) }
        }

        @JavascriptInterface
        fun isAvailable(): Boolean = true

        // Cold-start path for "Share -> DownloadThat": the page pulls the
        // shared URL once its auth flow completes (deliverPendingSharedUrl()
        // in index.html). Clears on read so a poll can't queue it twice.
        @JavascriptInterface
        fun consumePendingSharedUrl(): String? {
            val url = pendingSharedUrl
            pendingSharedUrl = null
            return url
        }
    }

    /**
     * Debug builds (what CI builds and what `gradle installDebug` gives a
     * developer) use a fixed password for reproducibility. Release builds —
     * the APKs actually meant for sideloading onto other people's phones —
     * generate a random one on first launch and persist it, so no two
     * installs of the distributed app share a credential.
     */
    private fun getOrCreatePassword(): String {
        if (BuildConfig.DEBUG) {
            return DEBUG_PASSWORD
        }
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        prefs.getString(PREFS_PASSWORD_KEY, null)?.let { return it }
        val bytes = ByteArray(18)
        SecureRandom().nextBytes(bytes)
        val generated = bytes.joinToString("") { "%02x".format(it) }
        prefs.edit().putString(PREFS_PASSWORD_KEY, generated).apply()
        return generated
    }

    /** Empty string means "licensing off" to android_entry.start() — see its docstring. */
    private fun resolveLicenseApiBase(): String = if (BuildConfig.DEBUG) "" else LICENSE_API_BASE

    private fun startPythonServer() {
        if (serverStarted) return
        serverStarted = true
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        Thread {
            try {
                val dataDir = filesDir.resolve("classydl-data").absolutePath
                // App-specific external storage, not internal filesDir: needs no
                // permission on any supported API level (scoped storage exempts an
                // app's own directory under Android/data/<package>/), and — unlike
                // internal storage — is reachable by a file manager and by `adb
                // shell` without root. Falls back to internal storage in the rare
                // case external storage isn't currently available (e.g. removed
                // SD card on a device that redirected it there).
                val outputDir = (getExternalFilesDir(null) ?: filesDir)
                    .resolve("classydl-downloads").absolutePath
                Python.getInstance()
                    .getModule("video_downloader.android_entry")
                    .callAttr(
                        "start", dataDir, outputDir, password, PORT, resolveFfmpegBinary(),
                        resolveLicenseApiBase(), BuildConfig.VERSION_NAME,
                    )
            } catch (e: Throwable) {
                Log.e(TAG, "Server thread crashed", e)
            }
        }.apply {
            isDaemon = true
            start()
        }
    }

    /**
     * The bundled ffmpeg CLI (cross-compiled for Android, see
     * .github/scripts/build_ffmpeg_android.sh) ships under jniLibs — Android's
     * package installer extracts those into nativeLibraryDir with execute
     * permission already set, which is one of the few app-private locations
     * still allowed to run arbitrary native executables post-scoped-storage.
     * Falls back to the plain "ffmpeg" command name if the bundled binary
     * isn't present (e.g. an older APK built before Phase 2b).
     */
    private fun resolveFfmpegBinary(): String {
        val bundled = java.io.File(applicationInfo.nativeLibraryDir, "libffmpeg.so")
        return if (bundled.exists()) bundled.absolutePath else "ffmpeg"
    }
}
