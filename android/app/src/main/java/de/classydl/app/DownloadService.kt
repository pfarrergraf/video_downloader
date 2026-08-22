package de.classydl.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File

/**
 * Foreground service that hosts the embedded Python server so downloads
 * survive the Activity being backgrounded/killed (permissions approved by
 * the repo owner 2026-07-07 — see docs/ANDROID_PERMISSIONS_2026-07-07.md).
 *
 * Notification flow: the Python publisher loop calls NotifierBridge
 * .onJobsChanged(json) about once per second (android_entry._jobs_snapshot) -
 * unconditionally, whether or not anything changed, so handleSnapshot() below
 * runs continuously even while the queue sits idle. Active jobs drive the
 * ongoing progress notification; completions get a one-shot notification
 * whose tap opens the file (same FileProvider path as android_bridge.open_file).
 *
 * Idle handling used to drop foreground status (and the notification) the
 * instant the queue emptied. That fixed a real tester complaint ("still says
 * downloading when it's done") but broke a different guarantee: a foreground
 * service is the ONLY thing keeping this process (and the embedded Python
 * server the WebView talks to) alive if the user backgrounds the app - Android
 * only grants OOM-killer immunity while a visible ongoing notification is up,
 * there is no "foreground but invisible". Backgrounding right after the last
 * download finished then had zero protection (caught by
 * background_survival_test.sh: server dead within 30s). The queue empties ->
 * notification switches to an honest, dismissible "all done" state (still a
 * real foreground notification, so the process stays protected) and only
 * after IDLE_GRACE_MS with nothing new does the service actually leave
 * foreground mode. The started service keeps the existing Python notifier
 * connection either way, for the next user-initiated queue item (see
 * MainActivity/AndroidBridge).
 */
class DownloadService : Service() {

    companion object {
        private const val CHANNEL_ID = "downloads"
        private const val ONGOING_NOTIFICATION_ID = 1
        private const val COMPLETED_NOTIFICATION_BASE = 1000
        // Comfortably above background_survival_test.sh's 30s backgrounding
        // sleep - the whole point is that the process is still
        // foreground-protected across that window, not just numerically past
        // it by a hair.
        private const val IDLE_GRACE_MS = 45_000L
    }

    private val notifiedCompletions = mutableSetOf<Int>()
    @Volatile private var inForeground = false
    private var idleShutdownScheduled = false
    private val handler = Handler(Looper.getMainLooper())
    private val idleShutdownRunnable = Runnable {
        idleShutdownScheduled = false
        inForeground = false
        stopForeground(STOP_FOREGROUND_REMOVE)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onDestroy() {
        handler.removeCallbacks(idleShutdownRunnable)
        super.onDestroy()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        goForeground(getString(R.string.notif_downloads_running))
        ServerRuntime.ensureStarted(applicationContext, NotifierBridge())
        // STICKY: if Android reclaims the process mid-download, the service
        // (and with it the server + queue recovery) is restarted.
        return START_STICKY
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        // Android 15+ gives dataSync services a shared six-hour background
        // budget and requires stopSelf() within seconds of this callback.
        // Mark queued/running work cancelled first so the Python workers stop
        // cooperatively instead of continuing without foreground protection.
        try {
            if (com.chaquo.python.Python.isStarted()) {
                com.chaquo.python.Python.getInstance()
                    .getModule("video_downloader.android_entry")
                    .callAttr("cancel_active_for_system_timeout")
            }
        } catch (error: Throwable) {
            android.util.Log.e("ClassyDL", "Could not cancel downloads after FGS timeout", error)
        } finally {
            handler.removeCallbacks(idleShutdownRunnable)
            idleShutdownScheduled = false
            inForeground = false
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf(startId)
        }
    }

    // Reached both from a user gesture (onStartCommand(), via the WebView
    // bridge's onDownloadQueued() - always foreground, always legal) and from
    // handleSnapshot() below, driven by the Python publisher thread on its
    // own ~1s cadence with no Activity in the call stack at all. The second
    // path is the one that can call this while the app is genuinely
    // backgrounded - e.g. a queued job's automatic retry-after-failure lands
    // after IDLE_GRACE_MS has already dropped foreground status and the user
    // has since backgrounded the app. On API 31+ that specific combination
    // (promoting a service to foreground from a background app state) is
    // exactly what ForegroundServiceStartNotAllowedException exists to
    // reject - Android's own guidance is to catch it, not prevent it, since
    // there is no reliable "am I currently foreground" check to gate the call
    // on beforehand. Caught as the plain IllegalStateException superclass so
    // this compiles and behaves identically on every API level instead of
    // needing an SDK-gated reference to the (API 31+ only) subclass.
    private fun goForeground(text: String) {
        val notification = buildOngoing(text, progressPct = null)
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(
                    ONGOING_NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
                )
            } else {
                startForeground(ONGOING_NOTIFICATION_ID, notification)
            }
            inForeground = true
        } catch (e: IllegalStateException) {
            // Not promoted, but not crashed either - the download itself
            // keeps running unprotected until the next legal chance to
            // promote (any onDownloadQueued() call, which only ever happens
            // from a live user gesture in the foreground).
            android.util.Log.w("ClassyDL", "Could not promote to foreground (app likely backgrounded)", e)
        }
    }

    /** Called from the Python publisher thread via Chaquopy — must be thread-safe. */
    inner class NotifierBridge {
        fun onJobsChanged(json: String) {
            try {
                handleSnapshot(JSONObject(json))
            } catch (e: Throwable) {
                android.util.Log.e("ClassyDL", "Bad jobs snapshot", e)
            }
        }
    }

    private fun handleSnapshot(snapshot: JSONObject) {
        val active = snapshot.optJSONArray("active")
        val completed = snapshot.optJSONArray("completed")

        if (completed != null) {
            for (i in 0 until completed.length()) {
                val job = completed.getJSONObject(i)
                val id = job.getInt("id")
                if (notifiedCompletions.add(id)) {
                    notifyCompleted(id, job.getString("filename"), job.getString("path"))
                }
            }
        }

        val activeCount = active?.length() ?: 0
        if (activeCount > 0) {
            if (idleShutdownScheduled) {
                // New work arrived inside the grace window - the service was
                // never actually out of foreground, just cancel the pending
                // drop instead of letting it fire under our feet later.
                handler.removeCallbacks(idleShutdownRunnable)
                idleShutdownScheduled = false
            }
            var downloaded = 0L
            var total = 0L
            var totalsKnown = true
            for (i in 0 until activeCount) {
                val job = active!!.getJSONObject(i)
                downloaded += job.optLong("downloaded_bytes", 0)
                val jobTotal = job.optLong("total_bytes", 0)
                if (jobTotal > 0) total += jobTotal else totalsKnown = false
            }
            val pct = if (totalsKnown && total > 0) ((downloaded * 100) / total).toInt() else null
            val text = resources.getQuantityString(R.plurals.notif_active_downloads, activeCount, activeCount)
            if (!inForeground) goForeground(text)
            notificationManager().notify(ONGOING_NOTIFICATION_ID, buildOngoing(text, pct))
        } else if (inForeground && !idleShutdownScheduled) {
            // The publisher polls every ~1s regardless of whether anything
            // changed, so this branch would otherwise run on every idle tick -
            // idleShutdownScheduled guards it to firing exactly once per
            // active-to-idle transition instead of continuously re-arming
            // (and, with postDelayed, endlessly pushing back) the timer.
            notificationManager().notify(
                ONGOING_NOTIFICATION_ID,
                buildOngoing(
                    getString(R.string.notif_idle),
                    progressPct = null,
                    ongoing = false,
                    icon = android.R.drawable.stat_sys_download_done,
                ),
            )
            idleShutdownScheduled = true
            handler.postDelayed(idleShutdownRunnable, IDLE_GRACE_MS)
        }
    }

    private fun buildOngoing(
        text: String,
        progressPct: Int?,
        ongoing: Boolean = true,
        icon: Int = android.R.drawable.stat_sys_download,
    ): Notification {
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(icon)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setContentIntent(contentIntent)
            .setOnlyAlertOnce(true)
            .setOngoing(ongoing)
            .apply {
                if (progressPct != null) setProgress(100, progressPct, false)
            }
            .build()
    }

    private fun notifyCompleted(jobId: Int, filename: String, path: String) {
        // Internal completions always open in DownloadThat's own player. This
        // avoids a system chooser and preserves the local-only playback rule.
        val contentIntent = try {
            val uri = FileProvider.getUriForFile(this, "de.classydl.app.fileprovider", File(path))
            val view = Intent(this, PlayerActivity::class.java)
                .setAction(PlayerActivity.ACTION_PLAY_INTERNAL)
                .setDataAndType(uri, MediaMimeTypes.forFile(File(path)))
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            PendingIntent.getActivity(
                this, jobId, view,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        } catch (e: Exception) {
            // File outside the provider paths or already gone — fall back to
            // opening the app instead of dropping the notification entirely.
            PendingIntent.getActivity(
                this, jobId, Intent(this, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(getString(R.string.notif_download_done))
            .setContentText(filename)
            .setContentIntent(contentIntent)
            .setAutoCancel(true)
            .build()
        notificationManager().notify(COMPLETED_NOTIFICATION_BASE + jobId, notification)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notif_channel_downloads),
                NotificationManager.IMPORTANCE_LOW,
            )
            notificationManager().createNotificationChannel(channel)
        }
    }

    private fun notificationManager(): NotificationManager =
        getSystemService(NOTIFICATION_SERVICE) as NotificationManager
}
