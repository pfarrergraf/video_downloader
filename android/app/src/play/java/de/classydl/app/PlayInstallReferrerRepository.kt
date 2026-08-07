package de.classydl.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.android.installreferrer.api.InstallReferrerClient
import com.android.installreferrer.api.InstallReferrerStateListener
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Reads Play's install referrer once, stores only delivery state, and retries
 * transient failures on a later app start. The server remains the source of
 * truth and can reject disabled/invalid claims without entitlement impact.
 */
class PlayInstallReferrerRepository(
    context: Context,
    private val entitlementApi: EntitlementApi,
) : InstallReferrerRepository {
    companion object {
        private const val TAG = "InstallReferrer"
        private const val PREFS = "classydl_affiliate_referrer"
        private const val STATE = "state"
        private const val ATTEMPTS = "attempts"
        private const val FINAL = "final"
        private const val RETRY = "retry"
        private const val MAX_ATTEMPTS = 3
        private val RETRY_DELAYS_MS = longArrayOf(0L, 60 * 60 * 1000L, 24 * 60 * 60 * 1000L)
    }

    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val handler = Handler(Looper.getMainLooper())
    private var client: InstallReferrerClient? = null
    private val closed = AtomicBoolean(false)

    override fun start() {
        if (!BuildConfig.AFFILIATE_ATTRIBUTION_CLIENT_ENABLED || closed.get()) return
        if (prefs.getString(STATE, null) == FINAL) return
        val attempts = prefs.getInt(ATTEMPTS, 0)
        if (attempts >= MAX_ATTEMPTS) return
        val delay = RETRY_DELAYS_MS[attempts.coerceAtMost(RETRY_DELAYS_MS.lastIndex)]
        handler.postDelayed({ connect(attempts) }, delay)
    }

    private fun connect(attempt: Int) {
        if (closed.get()) return
        prefs.edit().putInt(ATTEMPTS, attempt + 1).putString(STATE, RETRY).apply()
        val referrerClient = InstallReferrerClient.newBuilder(appContext).build()
        client = referrerClient
        referrerClient.startConnection(object : InstallReferrerStateListener {
            override fun onInstallReferrerSetupFinished(responseCode: Int) {
                if (closed.get()) return
                when (responseCode) {
                    InstallReferrerClient.InstallReferrerResponse.OK -> deliver(referrerClient)
                    InstallReferrerClient.InstallReferrerResponse.FEATURE_NOT_SUPPORTED -> finish(referrerClient)
                    else -> closeClient(referrerClient)
                }
            }

            override fun onInstallReferrerServiceDisconnected() {
                closeClient(referrerClient)
            }
        })
    }

    private fun deliver(referrerClient: InstallReferrerClient) {
        try {
            val details = referrerClient.installReferrer
            entitlementApi.submitInstallAttribution(
                details.installReferrer,
                details.referrerClickTimestampSeconds.takeIf { it > 0 },
                details.installBeginTimestampSeconds.takeIf { it > 0 },
            ) { result ->
                if (result.optBoolean("ok")) finish(referrerClient)
                else if (result.optInt("status", 500) in 400..499 || result.optString("error") == "affiliate_not_enabled") finish(referrerClient)
                else closeClient(referrerClient)
            }
        } catch (error: Exception) {
            Log.w(TAG, "Install Referrer read failed", error)
            closeClient(referrerClient)
        }
    }

    private fun finish(referrerClient: InstallReferrerClient) {
        prefs.edit().putString(STATE, FINAL).apply()
        closeClient(referrerClient)
    }

    private fun closeClient(referrerClient: InstallReferrerClient) {
        try { referrerClient.endConnection() } catch (_: Exception) { }
        if (client === referrerClient) client = null
    }

    override fun close() {
        closed.set(true)
        handler.removeCallbacksAndMessages(null)
        client?.let(::closeClient)
    }
}
