package de.classydl.app

import android.content.Context
import org.json.JSONObject

/**
 * Small client-side cache for a server-verified entitlement. The server is
 * always authoritative; cached Pro access expires after 72 hours while Free
 * functionality remains available.
 */
class EntitlementStore(context: Context) {
    companion object {
        const val OFFLINE_GRACE_MS = 72L * 60 * 60 * 1000
        private const val PREFS_NAME = "classydl_entitlement"
        private const val KEY_LICENSE = "license_key"
        private const val KEY_VERIFIED_AT = "verified_at"
    }

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun recordVerified(licenseKey: String, verifiedAt: Long = System.currentTimeMillis()) {
        require(licenseKey.isNotBlank())
        prefs.edit().putString(KEY_LICENSE, licenseKey).putLong(KEY_VERIFIED_AT, verifiedAt).apply()
    }

    fun clear() {
        // Keep the install-scoped device id (owned by EntitlementApi) stable;
        // otherwise a revocation/reactivation could incorrectly consume a
        // second server-side Android device slot.
        prefs.edit().remove(KEY_LICENSE).remove(KEY_VERIFIED_AT).apply()
    }

    fun licenseKey(): String? = prefs.getString(KEY_LICENSE, null)

    fun isPro(now: Long = System.currentTimeMillis()): Boolean =
        licenseKey() != null && LicenseCachePolicy.isInsideGrace(
            prefs.getLong(KEY_VERIFIED_AT, 0L),
            now,
        )

    fun statusJson(billingAvailable: Boolean): String = JSONObject()
        .put("billingAvailable", billingAvailable)
        .put("pro", isPro())
        .put("licenseKey", licenseKey() ?: JSONObject.NULL)
        .put("offlineGraceHours", 72)
        .toString()
}

object LicenseCachePolicy {
    fun isInsideGrace(verifiedAt: Long, now: Long): Boolean =
        verifiedAt > 0L && now >= verifiedAt && now - verifiedAt <= EntitlementStore.OFFLINE_GRACE_MS
}
