package de.classydl.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** POST-only license and Play-token API client; secrets never enter a URL. */
class EntitlementApi(context: Context, private val onResult: (JSONObject) -> Unit) {
    private val appContext = context.applicationContext
    private val executor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val deviceId = InstallIdentity.getOrCreate(appContext)

    fun verifyPurchase(token: String, productId: String, event: String) {
        post(
            "/api/play/purchases/verify",
            identityBody()
                .put("purchase_token", token)
                .put("product_id", productId)
                .put("package_name", "de.classydl.app")
                .put("app_version", BuildConfig.VERSION_NAME),
            reportResult = false,
            callback = { result ->
                result.put("_purchase_token", token)
                result.put("event", event)
                onResult(result)
            },
        )
    }

    fun confirmPurchaseDelivered(token: String) {
        post(
            "/api/play/purchases/delivered",
            identityBody().put("purchase_token", token),
            reportResult = false,
        )
    }

    fun validateLicense(licenseKey: String) {
        post(
            "/api/license/validate",
            identityBody()
                .put("key", licenseKey)
                .put("platform", "android")
                .put("app_version", BuildConfig.VERSION_NAME),
            validatedLicenseKey = licenseKey,
        )
    }

    fun close() {
        executor.shutdownNow()
    }

    private fun identityBody(): JSONObject = JSONObject()
        .put("device_id", deviceId)
        .put("device_id_scheme", DEVICE_ID_SCHEME)

    private fun post(
        path: String,
        body: JSONObject,
        validatedLicenseKey: String? = null,
        reportResult: Boolean = true,
        callback: ((JSONObject) -> Unit)? = null,
    ) {
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
                parsed.put("status", status)
                parsed.put("ok", status in 200..299 && parsed.optBoolean("ok", true))
                if (validatedLicenseKey != null) {
                    parsed.put("requested_license_key", validatedLicenseKey)
                    if (parsed.optBoolean("valid")) parsed.put("license_key", validatedLicenseKey)
                }
                syncEmbeddedLicenseIfActive(parsed)
                parsed
            } catch (error: Exception) {
                JSONObject().put("ok", false).put("error", "network_error")
            }
            if (callback != null) mainHandler.post { callback(result) }
            else if (reportResult) mainHandler.post { onResult(result) }
        }
    }

    /**
     * Native Play verification and the Python download queue keep separate
     * entitlement caches. Once the backend confirms Pro, force the same key
     * through the authenticated loopback /api/license route so the queue does
     * not remain Free for up to its normal six-hour validation TTL.
     */
    private fun syncEmbeddedLicenseIfActive(result: JSONObject) {
        val active = result.optBoolean(
            "entitled",
            result.optBoolean("valid", result.optBoolean("pro", result.optBoolean("active", false))),
        ) && result.optBoolean("device_allowed", true)
        val key = result.optString("license_key", result.optString("licenseKey"))
        if (!active || key.isBlank()) return

        repeat(20) {
            val synced = runCatching { LocalApiClient.syncLicense(appContext, key) }.getOrDefault(false)
            if (synced) return
            Thread.sleep(250L)
        }
        Log.w(TAG, "Verified entitlement could not be synced to the embedded license cache")
    }

    companion object {
        const val DEVICE_ID_SCHEME = "android-scoped-v1"
        private const val TAG = "ClassyDL"
    }
}
