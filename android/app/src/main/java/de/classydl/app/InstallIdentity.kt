package de.classydl.app

import android.content.Context
import android.provider.Settings
import java.security.MessageDigest
import java.util.UUID

/**
 * Stable, privacy-preserving Android identity used for device-limited licensing.
 *
 * This is a device-slot identity, not an install identity. A random UUID stored
 * only in app-private state disappears on uninstall and must never be the
 * authoritative device key for licensing.
 *
 * On API 26+ ANDROID_ID is scoped to app-signing key + Android user + device and
 * survives a normal uninstall/reinstall. DownloadThat never sends the raw
 * ANDROID_ID: it derives a namespaced SHA-256 value locally.
 */
object InstallIdentity {
    private const val PREFS_NAME = "classydl_entitlement"
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
        // install-scoped and therefore does not provide reinstall stability;
        // supported Android 8+ devices should normally always have ANDROID_ID.
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.getString(FALLBACK_KEY_DEVICE_ID, null)?.takeIf { it.isNotBlank() }?.let { return it }
        val generated = sha256Hex(DEVICE_NAMESPACE + "fallback:" + UUID.randomUUID())
        prefs.edit().putString(FALLBACK_KEY_DEVICE_ID, generated).apply()
        return generated
    }

    private fun sha256Hex(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
}
