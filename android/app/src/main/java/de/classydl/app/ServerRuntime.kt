package de.classydl.app

import android.content.Context
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.security.SecureRandom
import java.util.concurrent.CopyOnWriteArraySet
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Process-wide owner of the embedded loopback HTTP runtime. */
object ServerRuntime {
    const val PORT = 8420
    const val SERVER_URL = "http://127.0.0.1:$PORT"

    enum class State { STOPPED, STARTING, READY, FAILED }

    interface Listener {
        fun onRuntimeStateChanged(state: State) {}
        fun onJobsChanged(json: String) {}
    }

    private const val PREFS_NAME = "classydl_prefs"
    private const val PREFS_PASSWORD_KEY = "server_password"
    private const val DEBUG_PASSWORD = "classydl"
    private const val TAG = "ClassyDL"

    private val lock = Any()
    private val listeners = CopyOnWriteArraySet<Listener>()
    @Volatile private var appContext: Context? = null
    @Volatile private var state = State.STOPPED
    @Volatile private var readyLatch = CountDownLatch(1)

    fun currentState(): State = state

    fun addListener(listener: Listener) {
        listeners.add(listener)
        listener.onRuntimeStateChanged(state)
    }

    fun removeListener(listener: Listener) {
        listeners.remove(listener)
    }

    fun getOrCreatePassword(context: Context): String {
        if (BuildConfig.DEBUG) return DEBUG_PASSWORD
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.getString(PREFS_PASSWORD_KEY, null)?.let { return it }
        val bytes = ByteArray(18)
        SecureRandom().nextBytes(bytes)
        val generated = bytes.joinToString("") { "%02x".format(it) }
        prefs.edit().putString(PREFS_PASSWORD_KEY, generated).apply()
        return generated
    }

    /** Single-flight start. A FAILED runtime may be retried by the next caller. */
    fun ensureStarted(context: Context) {
        val appContext = context.applicationContext
        this.appContext = appContext
        synchronized(lock) {
            if (state == State.STARTING || state == State.READY) return
            readyLatch = CountDownLatch(1)
            transition(State.STARTING)
            if (!Python.isStarted()) Python.start(AndroidPlatform(appContext))
            Thread({ startPythonServer(appContext) }, "downloadthat-server-runtime").apply {
                isDaemon = true
                start()
            }
        }
    }

    fun awaitReady(timeoutMs: Long = 20_000L): Boolean {
        if (state == State.READY) return true
        return readyLatch.await(timeoutMs, TimeUnit.MILLISECONDS) && state == State.READY
    }

    fun setExecutionEnabled(enabled: Boolean): Boolean {
        if (enabled && !awaitReady()) return false
        if (!enabled && !Python.isStarted()) return true
        return runCatching {
            Python.getInstance().getModule("video_downloader.android_entry")
                .callAttr("set_execution_enabled", enabled)
            true
        }.onFailure { Log.e(TAG, "Could not change Python execution gate", it) }.getOrDefault(false)
    }

    fun hasPendingWork(): Boolean {
        if (!awaitReady(2_000L)) return false
        return runCatching {
            Python.getInstance().getModule("video_downloader.android_entry")
                .callAttr("has_pending_work").toBoolean()
        }.getOrDefault(false)
    }

    fun cancelActiveTransfers(): Int {
        if (state != State.READY) return 0
        return runCatching {
            Python.getInstance().getModule("video_downloader.android_entry")
                .callAttr("cancel_active_for_system_timeout").toInt()
        }.onFailure { Log.e(TAG, "Could not cancel transfers after foreground loss", it) }
            .getOrDefault(0)
    }

    private fun startPythonServer(appContext: Context) {
        try {
            val dataDir = appContext.filesDir.resolve("classydl-data").absolutePath
            val outputDir = (appContext.getExternalFilesDir(null) ?: appContext.filesDir)
                .resolve("classydl-downloads").absolutePath
            Python.getInstance().getModule("video_downloader.android_entry").callAttr(
                "start",
                dataDir,
                outputDir,
                getOrCreatePassword(appContext),
                PORT,
                resolveFfmpegBinary(appContext),
                resolveLicenseApiBase(),
                BuildConfig.VERSION_NAME,
                RuntimeBridge,
                resolveJsRuntimeBinary(appContext),
                InstallIdentity.getOrCreate(appContext),
                BuildConfig.PLAY_POLICY_RESTRICTED,
            )
            if (state == State.STARTING) transition(State.FAILED)
        } catch (error: Throwable) {
            Log.e(TAG, "Server runtime crashed", error)
            transition(State.FAILED)
        }
    }

    private fun transition(next: State) {
        state = next
        if (next == State.READY || next == State.FAILED) readyLatch.countDown()
        listeners.forEach { listener -> runCatching { listener.onRuntimeStateChanged(next) } }
        if (next == State.READY) appContext?.let(EntitlementCoordinator::applyDesiredAsync)
    }

    /** Chaquopy callback target; dispatch stays valid as services come and go. */
    object RuntimeBridge {
        @JvmStatic fun onServerReady() = transition(State.READY)
        @JvmStatic fun onJobsChanged(json: String) {
            listeners.forEach { listener -> runCatching { listener.onJobsChanged(json) } }
        }
    }

    private fun resolveLicenseApiBase(): String =
        if (BuildConfig.DEBUG) "" else BuildConfig.LICENSE_API_BASE_URL

    private fun resolveFfmpegBinary(context: Context): String {
        val bundled = java.io.File(context.applicationInfo.nativeLibraryDir, "libffmpeg.so")
        return if (bundled.exists()) bundled.absolutePath else "ffmpeg"
    }

    private fun resolveJsRuntimeBinary(context: Context): String {
        val bundled = java.io.File(context.applicationInfo.nativeLibraryDir, "libqjs.so")
        return if (bundled.exists()) bundled.absolutePath else ""
    }
}
