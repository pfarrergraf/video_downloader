package de.classydl.app

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject

/**
 * Small local persistence layer for retention features.
 *
 * Deliberately uses SharedPreferences instead of introducing Room only for a
 * bounded list of playback checkpoints. The store is private to this install,
 * follows allowBackup=false, and never uploads listening/viewing history.
 */
class PlaybackRetentionStore(context: Context) {
    data class Entry(
        val uri: String,
        val title: String,
        val mimeType: String?,
        val positionMs: Long,
        val durationMs: Long,
        val lastPlayedAtMs: Long,
    ) {
        val isMeaningfulResume: Boolean
            get() = positionMs >= MIN_RESUME_MS &&
                (durationMs <= 0L || positionMs < durationMs - COMPLETION_MARGIN_MS)
    }

    private val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    @Synchronized
    fun record(
        uri: String,
        title: String,
        mimeType: String?,
        positionMs: Long,
        durationMs: Long,
    ) {
        if (!isOwnedDownloadUri(uri)) return
        val items = recent(MAX_HISTORY).toMutableList()
        items.removeAll { it.uri == uri }
        items.add(
            0,
            Entry(
                uri = uri,
                title = title.ifBlank { "Media" },
                mimeType = mimeType,
                positionMs = positionMs.coerceAtLeast(0L),
                durationMs = durationMs.coerceAtLeast(0L),
                lastPlayedAtMs = System.currentTimeMillis(),
            ),
        )
        writeHistory(items.take(MAX_HISTORY))
    }

    @Synchronized
    fun get(uri: String): Entry? = recent(MAX_HISTORY).firstOrNull { it.uri == uri }

    @Synchronized
    fun remove(uri: String) {
        if (uri.isBlank()) return
        writeHistory(recent(MAX_HISTORY).filterNot { it.uri == uri })
    }

    @Synchronized
    fun recent(limit: Int = MAX_HISTORY): List<Entry> {
        val raw = prefs.getString(KEY_HISTORY, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    val uri = item.optString("uri")
                    if (!isOwnedDownloadUri(uri)) continue
                    add(
                        Entry(
                            uri = uri,
                            title = item.optString("title", "Media"),
                            mimeType = item.optString("mimeType").takeIf { it.isNotBlank() },
                            positionMs = item.optLong("positionMs", 0L),
                            durationMs = item.optLong("durationMs", 0L),
                            lastPlayedAtMs = item.optLong("lastPlayedAtMs", 0L),
                        ),
                    )
                    if (size >= limit.coerceIn(1, MAX_HISTORY)) break
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    @Synchronized
    fun clearHistory() {
        prefs.edit().remove(KEY_HISTORY).apply()
    }

    fun playbackSpeed(): Float = prefs.getFloat(KEY_SPEED, 1.0f).coerceIn(0.5f, 2.0f)

    fun setPlaybackSpeed(speed: Float) {
        prefs.edit().putFloat(KEY_SPEED, speed.coerceIn(0.5f, 2.0f)).apply()
    }

    fun sleepDeadlineMs(): Long = prefs.getLong(KEY_SLEEP_DEADLINE, 0L)

    fun setSleepTimerMinutes(minutes: Int) {
        if (minutes <= 0) {
            clearSleepTimer()
            return
        }
        val deadline = System.currentTimeMillis() + minutes.toLong() * 60_000L
        prefs.edit().putLong(KEY_SLEEP_DEADLINE, deadline).apply()
    }

    fun clearSleepTimer() {
        prefs.edit().remove(KEY_SLEEP_DEADLINE).apply()
    }

    fun sleepMinutesRemaining(): Int {
        val remaining = sleepDeadlineMs() - System.currentTimeMillis()
        if (remaining <= 0L) return 0
        return ((remaining + 59_999L) / 60_000L).toInt()
    }

    private fun writeHistory(items: List<Entry>) {
        val array = JSONArray()
        items.forEach { entry ->
            array.put(
                JSONObject()
                    .put("uri", entry.uri)
                    .put("title", entry.title)
                    .put("mimeType", entry.mimeType ?: "")
                    .put("positionMs", entry.positionMs)
                    .put("durationMs", entry.durationMs)
                    .put("lastPlayedAtMs", entry.lastPlayedAtMs),
            )
        }
        prefs.edit().putString(KEY_HISTORY, array.toString()).apply()
    }

    /**
     * Retention is deliberately limited to DownloadThat's own FileProvider
     * URIs. External providers can revoke temporary grants at any time, so
     * keeping them would create broken recent items.
     */
    fun isOwnedDownloadUri(uri: String): Boolean = runCatching {
        val parsed = Uri.parse(uri)
        parsed.scheme == "content" && parsed.authority == FILE_PROVIDER_AUTHORITY
    }.getOrDefault(false)

    companion object {
        private const val PREFS_NAME = "downloadthat_playback_retention"
        private const val KEY_HISTORY = "history_json"
        private const val KEY_SPEED = "playback_speed"
        private const val KEY_SLEEP_DEADLINE = "sleep_deadline_ms"
        private const val MAX_HISTORY = 50
        private const val MIN_RESUME_MS = 5_000L
        private const val COMPLETION_MARGIN_MS = 8_000L
        private const val FILE_PROVIDER_AUTHORITY = "de.classydl.app.fileprovider"
    }
}
