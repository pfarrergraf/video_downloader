package de.classydl.app

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.security.SecureRandom

/**
 * Owns starting the embedded Python server exactly once per process.
 *
 * Shared by DownloadService (which hosts the server so downloads survive the
 * Activity being backgrounded) and MainActivity (which needs the password for
 * the WebView auto-login). Extracted from MainActivity when the foreground
 * service was introduced.
 */
object ServerRuntime {

    const val PORT = 8420
    const val SERVER_URL = "http://127.0.0.1:$PORT"

    private const val PREFS_NAME = "classydl_prefs"
    private const val PREFS_PASSWORD_KEY = "server_password"

    // Fixed in debug builds so CI's download_pipeline_test.sh (and anyone
    // testing locally) can log in without needing to read it back out of
    // the app's SharedPreferences. Release builds (the ones actually
    // sideloaded onto other people's phones) always get a random
    // per-install password instead — see getOrCreatePassword().
    private const val DEBUG_PASSWORD = "classydl"

    // The POST license endpoint (pro/website/functions/api/license/validate.js)
    // is a Cloudflare Pages Function on the same deployment as the
    // marketing site. Only wired up for release builds (see
    // resolveLicenseApiBase()) so CI's debug-build pipeline tests keep
    // exercising the always-unrestricted path, unaffected by free-tier
    // limits.
    // Idempotency guard: the service (START_STICKY) and the Activity may
    // both ask for a start; python-side android_entry.start() additionally
    // handles a stray duplicate bind gracefully (EADDRINUSE + health probe).
    @Volatile private var serverStarted = false

    /**
     * Debug builds use a fixed password for reproducibility. Release builds
     * generate a random one on first launch and persist it, so no two
     * installs of the distributed app share a credential.
     */
    fun getOrCreatePassword(context: Context): String {
        if (BuildConfig.DEBUG) {
            return DEBUG_PASSWORD
        }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.getString(PREFS_PASSWORD_KEY, null)?.let { return it }
        val bytes = ByteArray(18)
        SecureRandom().nextBytes(bytes)
        val generated = bytes.joinToString("") { "%02x".format(it) }
        prefs.edit().putString(PREFS_PASSWORD_KEY, generated).apply()
        return generated
    }

    /** Empty string means "licensing off" to android_entry.start() — see its docstring. */
    private fun resolveLicenseApiBase(): String = if (BuildConfig.DEBUG) "" else BuildConfig.LICENSE_API_BASE_URL

    /**
     * The bundled ffmpeg CLI (cross-compiled for Android, see
     * .github/scripts/build_ffmpeg_android.sh) ships under jniLibs — Android's
     * package installer extracts those into nativeLibraryDir with execute
     * permission already set, which is one of the few app-private locations
     * still allowed to run arbitrary native executables post-scoped-storage.
     * Falls back to the plain "ffmpeg" command name if the bundled binary
     * isn't present (e.g. an older APK built before Phase 2b).
     */
    private fun resolveFfmpegBinary(context: Context): String {
        val bundled = java.io.File(context.applicationInfo.nativeLibraryDir, "libffmpeg.so")
        return if (bundled.exists()) bundled.absolutePath else "ffmpeg"
    }

    /**
     * Starts Python + the web server on a background thread (idempotent).
     * [notifier] is handed through to android_entry.start() — the Python
     * publisher loop calls its onJobsChanged(json) about once per second.
     */
    fun ensureStarted(context: Context, notifier: Any?) {
        if (serverStarted) return
        serverStarted = true
        val appContext = context.applicationContext
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(appContext))
        }
        val password = getOrCreatePassword(appContext)
        Thread {
            try {
                val dataDir = appContext.filesDir.resolve("classydl-data").absolutePath
                // App-specific external storage, not internal filesDir: needs no
                // permission on any supported API level (scoped storage exempts an
                // app's own directory under Android/data/<package>/), and — unlike
                // internal storage — is reachable by a file manager and by `adb
                // shell` without root. Falls back to internal storage in the rare
                // case external storage isn't currently available.
                val outputDir = (appContext.getExternalFilesDir(null) ?: appContext.filesDir)
                    .resolve("classydl-downloads").absolutePath
                Python.getInstance()
                    .getModule("video_downloader.android_entry")
                    .callAttr(
                        "start", dataDir, outputDir, password, PORT,
                        resolveFfmpegBinary(appContext),
                        resolveLicenseApiBase(), BuildConfig.VERSION_NAME, notifier,
                    )
            } catch (e: Throwable) {
                android.util.Log.e("ClassyDL", "Server thread crashed", e)
            }
        }.apply {
            isDaemon = true
            start()
        }
    }
}
