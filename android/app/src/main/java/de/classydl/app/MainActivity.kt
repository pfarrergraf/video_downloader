package de.classydl.app

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
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

        // TODO: replace with the real deployed Pages URL once deployed via
        // Cloudflare "Connect to Git" (see pro/README.md) — until then this is
        // an unreachable placeholder, which is safe: android_entry.py's
        // LicenseManager fails closed (free-tier) on any network error, it
        // never grants Pro just because the license server is unreachable.
        // Only wired up for release builds (see resolveLicenseApiBase()) so
        // CI's debug-build download_pipeline_test.sh — which never sets a
        // license key — keeps exercising the always-unrestricted path it
        // was written against, unaffected by free-tier limits.
        // The backend lives in pro/website/functions/api/ and is deployed as a
        // Cloudflare Pages project — the live URL will be
        // https://<your-project>.pages.dev (not a workers.dev URL).
        private const val LICENSE_API_BASE = "https://YOUR-PROJECT.pages.dev"

        // Idempotency guard: Android may recreate the Activity (e.g. on a
        // config change) without restarting the process, causing onCreate →
        // startPythonServer() to be called a second time. The second
        // run_server() call would fail to bind the already-occupied port 8420
        // (OSError: [Errno 98] Address already in use) and crash that thread —
        // harmlessly for the app itself but also redundantly starts a second
        // _run_downloads_publisher thread, doubling SQLite polling. This flag
        // prevents both issues. @Volatile ensures the write is immediately
        // visible to any thread that reads it after onCreate returns.
        @Volatile private var serverStarted = false
    }

    private var loadRetries = 0
    private lateinit var password: String

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        password = getOrCreatePassword()
        startPythonServer()

        val webView = findViewById<WebView>(R.id.webview)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        // Lets the splash screen's chime (Web Audio API, see static/index.html)
        // play immediately on load instead of being blocked by the browser-style
        // autoplay-requires-a-gesture policy — safe here since it's our own
        // contained WebView, not an arbitrary page.
        webView.settings.mediaPlaybackRequiresUserGesture = false
        webView.webViewClient = object : WebViewClient() {
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
                    .callAttr("start", dataDir, outputDir, password, PORT, resolveFfmpegBinary(), resolveLicenseApiBase())
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
