package de.classydl.app

import android.content.Context
import android.util.Log

/** Persistent desired entitlement state, converged into the Python runtime by revision. */
object EntitlementCoordinator {
    private const val PREFS = "classydl_entitlement_sync"
    private const val KEY_INITIALIZED = "initialized"
    private const val KEY_REVISION = "revision"
    private const val KEY_ACTION = "action"
    private const val KEY_LICENSE = "license_key"
    private const val KEY_CHANGED_AT = "changed_at"
    private const val TAG = "ClassyDL"
    private val lock = Any()

    data class DesiredState(
        val revision: Long,
        val action: String,
        val licenseKey: String?,
        val changedAt: Long,
    )

    fun ensureDesiredSet(context: Context, licenseKey: String): DesiredState =
        record(context, "SET", licenseKey, onlyIfDifferent = true)

    fun recordVerified(context: Context, licenseKey: String): DesiredState =
        record(context, "SET", licenseKey, onlyIfDifferent = true)

    fun recordRevoked(context: Context): DesiredState =
        record(context, "CLEAR", null, onlyIfDifferent = true)

    fun requestEpoch(context: Context): Long = synchronized(lock) {
        read(context)?.revision ?: 0L
    }

    /** Apply a callback only if no newer SET/CLEAR decision happened meanwhile. */
    fun applyVerifiedResult(context: Context, licenseKey: String, requestEpoch: Long): Boolean =
        synchronized(lock) {
            val current = read(context)
            if (current != null && current.revision > requestEpoch) return@synchronized false
            record(context, "SET", licenseKey, onlyIfDifferent = true)
            EntitlementStore(context).recordVerified(licenseKey)
            true
        }

    /** Authenticated revocations are also ordered, so an old token can't revoke a repurchase. */
    fun applyRevokedResult(context: Context, requestEpoch: Long): Boolean = synchronized(lock) {
        val current = read(context)
        if (current != null && current.revision > requestEpoch) return@synchronized false
        record(context, "CLEAR", null, onlyIfDifferent = true)
        EntitlementStore(context).clear()
        true
    }

    fun applyDesired(context: Context, timeoutMs: Long = 20_000L): Boolean {
        val desired = read(context) ?: return true
        ServerRuntime.ensureStarted(context)
        if (!ServerRuntime.awaitReady(timeoutMs)) return false
        return LocalApiClient.syncEntitlement(context, desired)
    }

    fun applyDesiredAsync(context: Context) {
        val appContext = context.applicationContext
        Thread({
            if (!applyDesired(appContext)) Log.w(TAG, "Entitlement convergence is still pending")
        }, "downloadthat-entitlement-sync").apply { isDaemon = true }.start()
    }

    fun read(context: Context): DesiredState? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(KEY_INITIALIZED, false)) return null
        return DesiredState(
            revision = prefs.getLong(KEY_REVISION, 0L),
            action = prefs.getString(KEY_ACTION, "CLEAR") ?: "CLEAR",
            licenseKey = prefs.getString(KEY_LICENSE, null),
            changedAt = prefs.getLong(KEY_CHANGED_AT, 0L),
        )
    }

    private fun record(
        context: Context,
        action: String,
        licenseKey: String?,
        onlyIfDifferent: Boolean,
    ): DesiredState = synchronized(lock) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val current = read(context)
        if (
            onlyIfDifferent && current != null && current.action == action &&
            current.licenseKey == licenseKey
        ) return@synchronized current
        val next = DesiredState(
            revision = (current?.revision ?: 0L) + 1L,
            action = action,
            licenseKey = licenseKey,
            changedAt = System.currentTimeMillis(),
        )
        val editor = prefs.edit()
            .putBoolean(KEY_INITIALIZED, true)
            .putLong(KEY_REVISION, next.revision)
            .putString(KEY_ACTION, next.action)
            .putLong(KEY_CHANGED_AT, next.changedAt)
        if (licenseKey == null) editor.remove(KEY_LICENSE) else editor.putString(KEY_LICENSE, licenseKey)
        check(editor.commit()) { "Could not persist entitlement revision" }
        next
    }
}
