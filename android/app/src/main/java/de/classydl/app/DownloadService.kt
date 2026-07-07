package de.classydl.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
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
 * .onJobsChanged(json) about once per second (android_entry._jobs_snapshot).
 * Active jobs drive the ongoing progress notification; completions get a
 * one-shot notification whose tap opens the file (same FileProvider path as
 * android_bridge.open_file). When the queue has been idle for a while the
 * service takes itself out of the foreground and stops — the Python server
 * keeps running in-process while Android keeps the process alive, and any
 * new download restarts the service (see MainActivity/AndroidBridge).
 */
class DownloadService : Service() {

    companion object {
        private const val CHANNEL_ID = "downloads"
        private const val ONGOING_NOTIFICATION_ID = 1
        private const val COMPLETED_NOTIFICATION_BASE = 1000
        // ~30s of consecutive idle snapshots (1s cadence) before leaving the
        // foreground: long enough that back-to-back queue additions don't
        // flap the notification, short enough not to camp in the tray.
        private const val IDLE_TICKS_BEFORE_STOP = 30
    }

    private val notifiedCompletions = mutableSetOf<Int>()
    private var idleTicks = 0
    @Volatile private var inForeground = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        goForeground(getString(R.string.notif_downloads_running))
        idleTicks = 0
        ServerRuntime.ensureStarted(applicationContext, NotifierBridge())
        // STICKY: if Android reclaims the process mid-download, the service
        // (and with it the server + queue recovery) is restarted.
        return START_STICKY
    }

    private fun goForeground(text: String) {
        val notification = buildOngoing(text, progressPct = null)
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
            idleTicks = 0
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
        } else if (inForeground) {
            idleTicks++
            if (idleTicks >= IDLE_TICKS_BEFORE_STOP) {
                inForeground = false
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
    }

    private fun buildOngoing(text: String, progressPct: Int?): Notification {
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setContentIntent(contentIntent)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .apply {
                if (progressPct != null) setProgress(100, progressPct, false)
            }
            .build()
    }

    private fun notifyCompleted(jobId: Int, filename: String, path: String) {
        // Tap opens the file in a player — the same FileProvider handoff
        // android_bridge.open_file uses from the in-app "View" button.
        val contentIntent = try {
            val uri = FileProvider.getUriForFile(this, "de.classydl.app.fileprovider", File(path))
            val view = Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, contentResolver.getType(uri) ?: "*/*")
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
