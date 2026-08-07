package de.classydl.app

import android.content.Context
import org.json.JSONObject
import java.util.UUID

/**
 * One install-scoped identifier shared by the native Billing bridge and the
 * embedded Python license manager. Using two random IDs for the same Android
 * install makes the server correctly reject one of them as a second device.
 */
object InstallIdentity {
    private const val PREFS_NAME = "classydl_entitlement"
    private const val KEY_DEVICE_ID = "device_id"

    @Synchronized
    fun getOrCreate(context: Context): String {
        val appContext = context.applicationContext
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val nativeId = prefs.getString(KEY_DEVICE_ID, null)?.takeIf { it.isNotBlank() }

        // Existing releases persisted the Python-side ID first. Prefer it
        // during migration because the backend device slot already belongs to
        // that value; then copy it into SharedPreferences for native Billing.
        val legacyPythonId = runCatching {
            val stateFile = appContext.filesDir.resolve("classydl-data/license.json")
            if (!stateFile.isFile) null else JSONObject(stateFile.readText())
                .optString("device_id")
                .takeIf { it.isNotBlank() }
        }.getOrNull()

        val canonical = legacyPythonId ?: nativeId ?: UUID.randomUUID().toString()
        if (nativeId != canonical) prefs.edit().putString(KEY_DEVICE_ID, canonical).apply()
        return canonical
    }
}
