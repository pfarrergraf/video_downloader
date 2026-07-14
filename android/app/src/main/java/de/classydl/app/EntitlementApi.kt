package de.classydl.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** POST-only license and Play-token API client; secrets never enter a URL. */
class EntitlementApi(context: Context, private val onResult: (JSONObject) -> Unit) {
    companion object {
        private const val PREFS_NAME = "classydl_entitlement"
        private const val KEY_DEVICE_ID = "device_id"
    }

    private val executor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val deviceId = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        .let { prefs ->
            prefs.getString(KEY_DEVICE_ID, null) ?: java.util.UUID.randomUUID().toString().also {
                prefs.edit().putString(KEY_DEVICE_ID, it).apply()
            }
        }

    fun verifyPurchase(token: String, productId: String) {
        post(
            "/api/play/purchases/verify",
            JSONObject()
                .put("purchase_token", token)
                .put("product_id", productId)
                .put("package_name", "de.classydl.app"),
        )
    }

    fun validateLicense(licenseKey: String) {
        post(
            "/api/license/validate",
            JSONObject()
                .put("key", licenseKey)
                .put("platform", "android")
                .put("device_id", deviceId)
                .put("app_version", BuildConfig.VERSION_NAME),
            validatedLicenseKey = licenseKey,
        )
    }

    fun close() {
        executor.shutdownNow()
    }

    private fun post(path: String, body: JSONObject, validatedLicenseKey: String? = null) {
        executor.execute {
            val result = try {
                val connection = (URL(BuildConfig.LICENSE_API_BASE_URL + path).openConnection() as HttpURLConnection)
                connection.requestMethod = "POST"
                connection.connectTimeout = 10_000
                connection.readTimeout = 15_000
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                val status = connection.responseCode
                val stream = if (status in 200..299) connection.inputStream else connection.errorStream
                val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                connection.disconnect()
                val parsed = if (response.isBlank()) JSONObject() else JSONObject(response)
                parsed.put("ok", status in 200..299 && parsed.optBoolean("ok", true))
                if (validatedLicenseKey != null) {
                    parsed.put("requested_license_key", validatedLicenseKey)
                    if (parsed.optBoolean("valid")) parsed.put("license_key", validatedLicenseKey)
                }
                parsed
            } catch (error: Exception) {
                JSONObject().put("ok", false).put("error", "network_error")
            }
            mainHandler.post { onResult(result) }
        }
    }
}
