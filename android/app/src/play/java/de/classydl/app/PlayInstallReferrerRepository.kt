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
        private const val NOT_STARTED = "not_started"
        private const val RETRYABLE = "retryable"
        private const val UNAVAILABLE = "unavailable"
        private const val SUBMITTED = "submitted"
        private const val RETRY = RETRYABLE
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
        val state = prefs.getString(STATE, null)
        if (state == UNAVAILABLE || state == SUBMITTED || state == FINAL) return
        val attempts = prefs.getInt(ATTEMPTS, 0)
        if (attempts >= MAX_ATTEMPTS) return
        val delay = RETRY_DELAYS_MS[attempts.coerceAtMost(RETRY_DELAYS_MS.lastIndex)]
        prefs.edit().putString(STATE, if (state == null) NOT_STARTED else RETRYABLE).apply()
        handler.postDelayed({ connect(attempts) }, delay)
    }

    private fun connect(attempt: Int) {
        if (closed.get()) return
        prefs.edit().putInt(ATTEMPTS, attempt + 1).putString(STATE, RETRY).apply()
        val referrerClient = InstallReferrerClient.newBuilder(appContext).build()
        client = referrerClient
        try {
            referrerClient.startConnection(object : InstallReferrerStateListener {
                override fun onInstallReferrerSetupFinished(responseCode: Int) {
                    if (closed.get()) return
                    when (responseCode) {
                        InstallReferrerClient.InstallReferrerResponse.OK -> deliver(referrerClient)
                        InstallReferrerClient.InstallReferrerResponse.FEATURE_NOT_SUPPORTED -> unavailable(referrerClient)
                        else -> retryable(referrerClient)
                    }
                }

                override fun onInstallReferrerServiceDisconnected() {
                    retryable(referrerClient)
                }
            })
        } catch (error: Exception) {
            Log.w(TAG, "Install Referrer connection failed", error)
            retryable(referrerClient)
        }
    }

    private fun deliver(referrerClient: InstallReferrerClient) {
        try {
            val details = referrerClient.installReferrer
            if (details.installReferrer.isBlank() || details.installReferrer.length > 512) {
                unavailable(referrerClient)
                return
            }
            entitlementApi.submitInstallAttribution(
                details.installReferrer,
                details.referrerClickTimestampSeconds.takeIf { it > 0 },
                details.installBeginTimestampSeconds.takeIf { it > 0 },
            ) { result ->
                if (result.optBoolean("ok")) submitted(referrerClient)
                else if (result.optInt("status", 500) in 400..499 || result.optString("error") == "affiliate_not_enabled") finish(referrerClient)
                else retryable(referrerClient)
            }
        } catch (error: Exception) {
            Log.w(TAG, "Install Referrer read failed", error)
            retryable(referrerClient)
        }
    }

    private fun unavailable(referrerClient: InstallReferrerClient) {
        prefs.edit().putString(STATE, UNAVAILABLE).apply()
        closeClient(referrerClient)
    }

    private fun submitted(referrerClient: InstallReferrerClient) {
        prefs.edit().putString(STATE, SUBMITTED).apply()
        closeClient(referrerClient)
    }

    private fun retryable(referrerClient: InstallReferrerClient) {
        prefs.edit().putString(STATE, RETRYABLE).apply()
        closeClient(referrerClient)
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
