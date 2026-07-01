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

/**
 * Hosts the Gothic UI in a WebView, backed by the same Python web server used on
 * Termux — see video_downloader/android_entry.py for the Chaquopy entry point.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ClassyDL"
        private const val PORT = 8420
        // TODO(Phase 1 follow-up): prompt for/store a real password instead of a
        // hardcoded default; this only binds to 127.0.0.1 so the immediate risk is
        // low, but it shouldn't stay hardcoded once this leaves the scaffold stage.
        private const val PASSWORD = "classydl"
        private const val SERVER_URL = "http://127.0.0.1:$PORT"
        private const val MAX_LOAD_RETRIES = 20
    }

    private var loadRetries = 0

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        startPythonServer()

        val webView = findViewById<WebView>(R.id.webview)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
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
        }
        webView.loadUrl(SERVER_URL)
    }

    private fun startPythonServer() {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        Thread {
            try {
                val dataDir = filesDir.resolve("classydl-data").absolutePath
                val outputDir = filesDir.resolve("classydl-downloads").absolutePath
                Python.getInstance()
                    .getModule("video_downloader.android_entry")
                    .callAttr("start", dataDir, outputDir, PASSWORD, PORT)
            } catch (e: Throwable) {
                Log.e(TAG, "Server thread crashed", e)
            }
        }.apply {
            isDaemon = true
            start()
        }
    }
}
