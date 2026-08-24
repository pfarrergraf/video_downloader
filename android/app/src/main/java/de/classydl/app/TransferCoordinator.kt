package de.classydl.app

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** User-gesture-bound handshake between queue producers and DownloadService. */
object TransferCoordinator {
    private val foregroundConfirmations = ConcurrentHashMap<String, CountDownLatch>()

    fun beginTransfer(context: Context): String {
        val id = UUID.randomUUID().toString()
        val confirmation = CountDownLatch(1)
        foregroundConfirmations[id] = confirmation
        val intent = Intent(context, DownloadService::class.java)
            .setAction(DownloadService.ACTION_BEGIN_TRANSFER)
            .putExtra(DownloadService.EXTRA_TRANSFER_ID, id)
        ContextCompat.startForegroundService(context, intent)
        if (!confirmation.await(5, TimeUnit.SECONDS)) {
            completeTransfer(context, id, queued = false)
            return ""
        }
        ServerRuntime.ensureStarted(context)
        if (!ServerRuntime.awaitReady() || !EntitlementCoordinator.applyDesired(context)) {
            completeTransfer(context, id, queued = false)
            return ""
        }
        if (!ServerRuntime.setExecutionEnabled(true)) {
            completeTransfer(context, id, queued = false)
            return ""
        }
        return id
    }

    fun onForegroundConfirmed(id: String) {
        foregroundConfirmations.remove(id)?.countDown()
    }

    fun completeTransfer(context: Context, id: String, queued: Boolean) {
        foregroundConfirmations.remove(id)?.countDown()
        if (id.isBlank()) return
        val intent = Intent(context, DownloadService::class.java)
            .setAction(DownloadService.ACTION_COMPLETE_TRANSFER)
            .putExtra(DownloadService.EXTRA_TRANSFER_ID, id)
            .putExtra(DownloadService.EXTRA_QUEUED, queued)
        context.startService(intent)
    }
}
