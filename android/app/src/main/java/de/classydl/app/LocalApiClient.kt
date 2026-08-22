package de.classydl.app

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Native client for the app's already-running authenticated loopback API. */
object LocalApiClient {
    data class QueueResult(val ok: Boolean, val jobId: Int? = null, val error: String? = null)

    fun enqueue(context: Context, source: String, audioOnly: Boolean): QueueResult {
        val cookie = login(context)
            ?: return QueueResult(false, error = context.getString(R.string.search_local_auth_failed))

        val settings = request("GET", "/api/settings", payload = null, cookie = cookie)
        val termsAccepted = settings.code in 200..299 && runCatching {
            JSONObject(settings.body).optBoolean("terms_accepted", false)
        }.getOrDefault(false)
        if (!termsAccepted) {
            return QueueResult(false, error = context.getString(R.string.search_terms_required))
        }

        val payload = JSONObject()
            .put("source", source)
            .put("audio_only", audioOnly)
        val response = request("POST", "/api/queue", payload, cookie)
        if (response.code !in 200..299) {
            val detail = runCatching { JSONObject(response.body).optString("detail") }.getOrNull()
            return QueueResult(
                false,
                error = detail?.takeIf { it.isNotBlank() }
                    ?: context.getString(R.string.search_queue_failed),
            )
        }
        val jobId = runCatching { JSONObject(response.body).getInt("job_id") }.getOrNull()
        return QueueResult(
            jobId != null,
            jobId = jobId,
            error = if (jobId == null) context.getString(R.string.search_queue_failed) else null,
        )
    }

    /**
     * Push a newly verified native/Play entitlement into the embedded Python
     * LicenseManager immediately. Its normal validation cache is six hours;
     * without this forced set-key path, a reinstall could successfully reclaim
     * its server-side slot through Play while the download queue still cached a
     * pre-restore device_allowed=false result.
     */
    fun syncLicense(context: Context, licenseKey: String): Boolean {
        if (licenseKey.isBlank()) return false
        val cookie = login(context) ?: return false
        val response = request(
            "POST",
            "/api/license",
            JSONObject().put("key", licenseKey),
            cookie,
        )
        return response.code in 200..299
    }

    private fun login(context: Context): String? {
        val password = ServerRuntime.getOrCreatePassword(context)
        val payload = JSONObject().put("password", password)
        val response = request("POST", "/api/login", payload, cookie = null)
        if (response.code !in 200..299) return null
        return response.setCookie?.substringBefore(';')?.takeIf { it.isNotBlank() }
    }

    private data class Response(val code: Int, val body: String, val setCookie: String?)

    private fun request(method: String, path: String, payload: JSONObject?, cookie: String?): Response {
        val connection = URL(ServerRuntime.SERVER_URL + path).openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = method
            connection.connectTimeout = 5_000
            connection.readTimeout = 20_000
            connection.setRequestProperty("Accept", "application/json")
            cookie?.let { connection.setRequestProperty("Cookie", it) }
            if (payload != null) {
                val bytes = payload.toString().toByteArray(Charsets.UTF_8)
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(bytes.size)
                connection.outputStream.use { it.write(bytes) }
            }
            val code = connection.responseCode
            val stream = if (code >= 400) connection.errorStream else connection.inputStream
            val body = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            Response(code, body, connection.getHeaderField("Set-Cookie"))
        } finally {
            connection.disconnect()
        }
    }
}
