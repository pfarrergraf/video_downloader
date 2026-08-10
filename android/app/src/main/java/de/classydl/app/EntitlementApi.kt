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
    private val executor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val deviceId = InstallIdentity.getOrCreate(context)

    fun checkPurchaseEligibility(onChecked: (JSONObject) -> Unit) {
        post(
            "/api/play/purchases/eligibility",
            JSONObject().put("device_id", deviceId),
            reportResult = false,
            callback = onChecked,
        )
    }

    fun verifyPurchase(token: String, productId: String, event: String) {
        post(
            "/api/play/purchases/verify",
            JSONObject()
                .put("purchase_token", token)
                .put("product_id", productId)
                .put("package_name", "de.classydl.app")
                .put("device_id", deviceId),
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
            JSONObject()
                .put("purchase_token", token)
                .put("device_id", deviceId),
            reportResult = false,
        )
    }

    fun requestRefund(token: String, reason: String) {
        post(
            "/api/play/refunds/request",
            JSONObject()
                .put("purchase_token", token)
                .put("device_id", deviceId)
                .put("reason", reason),
            reportResult = false,
            callback = { result ->
                result.put("_purchase_token", token)
                result.put("event", "refund")
                onResult(result)
            },
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

    fun submitInstallAttribution(
        referrer: String,
        referrerClickTimestampSeconds: Long?,
        appInstallTimestampSeconds: Long?,
        onSubmitted: (JSONObject) -> Unit,
    ) {
        val body = JSONObject()
            .put("install_id", deviceId)
            .put("referrer", referrer)
        if (referrerClickTimestampSeconds != null) body.put("referrer_click_timestamp_seconds", referrerClickTimestampSeconds)
        if (appInstallTimestampSeconds != null) body.put("app_install_timestamp_seconds", appInstallTimestampSeconds)
        post("/api/affiliate/attributions", body, reportResult = false, callback = onSubmitted)
    }

    fun close() {
        executor.shutdownNow()
    }

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
                parsed
            } catch (error: Exception) {
                JSONObject().put("ok", false).put("error", "network_error")
            }
            if (callback != null) mainHandler.post { callback(result) }
            else if (reportResult) mainHandler.post { onResult(result) }
        }
    }
}
