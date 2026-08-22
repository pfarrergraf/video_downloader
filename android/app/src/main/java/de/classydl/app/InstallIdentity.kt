package de.classydl.app

import android.content.Context
import android.provider.Settings
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID

/**
 * Stable, privacy-preserving Android identity used for device-limited licensing.
 *
 * Important: this is a device-slot identity, not an install identity. A random
 * UUID stored only in SharedPreferences/app-private files disappears on uninstall
 * and therefore must never be the authoritative device key for licensing.
 *
 * On API 26+ ANDROID_ID is scoped to app-signing key + Android user + device and
 * survives a normal uninstall/reinstall. We never send the raw ANDROID_ID: the
 * app derives a namespaced SHA-256 value locally.
 *
 * Existing releases used a random per-install UUID. [legacyForMigration] exposes
 * that previous value, when still available, so the backend can atomically move
 * the existing activation to the stable identity during a normal update.
 */
object InstallIdentity {
    private const val PREFS_NAME = "classydl_entitlement"
    // Historical key. Keep reading it for migration; do not overwrite it with
    // the stable identity because that would destroy our migration proof.
    private const val LEGACY_KEY_DEVICE_ID = "device_id"
    private const val FALLBACK_KEY_DEVICE_ID = "device_id_fallback_v2"
    private const val DEVICE_NAMESPACE = "downloadthat-license-device-v1:"

    @Synchronized
    fun getOrCreate(context: Context): String {
        val appContext = context.applicationContext
        val androidId = Settings.Secure.getString(
            appContext.contentResolver,
            Settings.Secure.ANDROID_ID,
        )?.trim()?.takeIf { it.isNotEmpty() }

        if (androidId != null) {
            return sha256Hex(DEVICE_NAMESPACE + androidId)
        }

        // Defensive fallback for a broken/non-standard device. This fallback is
        // install-scoped and therefore does NOT satisfy reinstall stability; it
        // exists only so licensing still has a bounded identifier instead of
        // crashing. Android 8+ devices should normally always have ANDROID_ID.
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.getString(FALLBACK_KEY_DEVICE_ID, null)?.takeIf { it.isNotBlank() }?.let { return it }
        val generated = sha256Hex(DEVICE_NAMESPACE + "fallback:" + UUID.randomUUID())
        prefs.edit().putString(FALLBACK_KEY_DEVICE_ID, generated).apply()
        return generated
    }

    /**
     * Previous random install identity, if this installation predates the
     * reinstall-stable scheme. Returned only for one-time server migration.
     */
    @Synchronized
    fun legacyForMigration(context: Context): String? {
        val appContext = context.applicationContext
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val nativeId = prefs.getString(LEGACY_KEY_DEVICE_ID, null)?.takeIf { it.isNotBlank() }

        // Older builds often persisted the Python-side identity first. That was
        // the canonical value copied into SharedPreferences and is most likely
        // the value which currently owns the backend activation slot.
        val legacyPythonId = runCatching {
            val stateFile = appContext.filesDir.resolve("classydl-data/license.json")
            if (!stateFile.isFile) null else JSONObject(stateFile.readText())
                .optString("device_id")
                .takeIf { it.isNotBlank() }
        }.getOrNull()

        val stable = getOrCreate(appContext)
        return (legacyPythonId ?: nativeId)?.takeIf { it != stable }
    }

    private fun sha256Hex(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
}
