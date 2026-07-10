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
import org.json.JSONObject

/**
 * Hosts the Gothic UI in a WebView, backed by the same Python web server used on
 * Termux — see video_downloader/android_entry.py for the Chaquopy entry point.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ClassyDL"
        private const val SERVER_URL = ServerRuntime.SERVER_URL
        private const val MAX_LOAD_RETRIES = 20
        private const val PREFS_NAME = "classydl_prefs"

        // First http(s) URL in a shared text - YouTube and most apps share
        // "Some title https://youtu.be/..." rather than a bare URL.
        private val SHARED_URL_REGEX = Regex("""https?://\S+""")

        private const val PREFS_LAST_CLIPBOARD_KEY = "last_clipboard_suggestion"
        private const val PREFS_NOTIF_ASKED_KEY = "notification_permission_asked"
    }

    private var loadRetries = 0
    private lateinit var password: String
    private lateinit var webView: WebView
    private lateinit var folderPickerLauncher: ActivityResultLauncher<Uri?>
    private lateinit var notificationPermissionLauncher: ActivityResultLauncher<String>

    // A URL shared into the app, waiting for the web UI to be ready.
    // @Volatile: written on the UI thread, read by the WebView's JS-bridge
    // thread (consumePendingSharedUrl).
    @Volatile private var pendingSharedUrl: String? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        password = ServerRuntime.getOrCreatePassword(this)
        // The Python server lives in DownloadService (a dataSync foreground
        // service) so downloads keep running when this Activity is
        // backgrounded or destroyed — see docs/ANDROID_PERMISSIONS_2026-07-07.md.
        startDownloadService()

        // Must be registered before STARTED (i.e. here in onCreate, not lazily
        // inside the bridge call) — ActivityResultRegistry throws otherwise.
        folderPickerLauncher = registerForActivityResult(
            ActivityResultContracts.OpenDocumentTree(),
        ) { uri -> onFolderPicked(uri) }
        notificationPermissionLauncher = registerForActivityResult(
            ActivityResultContracts.RequestPermission(),
        ) { /* granted or not, the service degrades gracefully either way */ }

        AffiliateReferral.capture(this, intent)
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
                val outboundUrl = AffiliateReferral.rewritePricingUrl(this@MainActivity, url)
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, outboundUrl).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                } catch (e: Exception) {
                    Log.e(TAG, "No app to handle $outboundUrl", e)
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
        AffiliateReferral.capture(this, intent)
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
        // Diagnostic detail (not just true/false): distinguishes "the page's
        // script never even defined onSharedUrl" from "onSharedUrl ran but the
        // login overlay was still up" from "it ran fully visible" - logged so a
        // CI failure (share_intent_test.sh) shows which of the three happened
        // instead of just "the job never appeared".
        webView.evaluateJavascript(
            """
            (function(){
                if (!window.onSharedUrl) return 'no-handler';
                var appEl = document.getElementById('app');
                var wasHidden = appEl && appEl.classList.contains('hidden');
                window.onSharedUrl($quoted);
                return wasHidden ? 'handler-app-hidden' : 'handler-app-visible';
            })();
            """.trimIndent(),
        ) { result ->
            Log.i(TAG, "Shared URL delivery result: $result")
            if (result != null && result.contains("handler") && pendingSharedUrl == url) {
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

        // Called by the page whenever a download is queued: restarts the
        // foreground service if it idled out (so this download's progress
        // survives backgrounding) and triggers the one-time contextual
        // notification-permission request.
        @JavascriptInterface
        fun onDownloadQueued() {
            runOnUiThread {
                startDownloadService()
                maybeRequestNotificationPermission()
            }
        }
    }

    /** Starts (or re-starts, e.g. after it idled out) the foreground service. */
    private fun startDownloadService() {
        val intent = Intent(this, DownloadService::class.java)
        androidx.core.content.ContextCompat.startForegroundService(this, intent)
    }

    /**
     * Contextual POST_NOTIFICATIONS request: asked once, right after the
     * user's first download starts (when a progress notification is about to
     * exist and the request makes sense to them) — never at app launch. A
     * denial is final from our side: the service simply runs without visible
     * notifications on API 33+.
     */
    private fun maybeRequestNotificationPermission() {
        if (android.os.Build.VERSION.SDK_INT < 33) return
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        if (prefs.getBoolean(PREFS_NOTIF_ASKED_KEY, false)) return
        prefs.edit().putBoolean(PREFS_NOTIF_ASKED_KEY, true).apply()
        if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) !=
            android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
