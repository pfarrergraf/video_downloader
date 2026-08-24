package de.classydl.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.net.Uri
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONException
import java.io.File
import java.security.MessageDigest

/** Private, transactional source of truth for local media and playlists. */
class MediaLibraryStore(private val context: Context) : SQLiteOpenHelper(
    context.applicationContext, DATABASE_NAME, null, DATABASE_VERSION,
) {
    data class Media(
        val id: String, val uri: String, val relativePath: String?, val title: String,
        val mimeType: String?, val durationMs: Long, val positionMs: Long,
        val addedAtMs: Long, val lastPlayedAtMs: Long?,
    ) {
        val isMeaningfulResume: Boolean get() = positionMs >= 5_000L &&
            (durationMs <= 0L || positionMs < durationMs - 8_000L)
    }
    data class Playlist(val id: Long, val name: String, val createdAtMs: Long, val updatedAtMs: Long)

    init { writableDatabase; migrateLegacyHistory() }

    override fun onConfigure(db: SQLiteDatabase) { db.setForeignKeyConstraintsEnabled(true) }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE media (
            id TEXT PRIMARY KEY, uri TEXT NOT NULL UNIQUE, relative_path TEXT,
            title TEXT NOT NULL, mime_type TEXT, duration_ms INTEGER NOT NULL DEFAULT 0,
            position_ms INTEGER NOT NULL DEFAULT 0, added_at_ms INTEGER NOT NULL,
            last_played_at_ms INTEGER)""")
        db.execSQL("""CREATE TABLE playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL)""")
        db.execSQL("""CREATE TABLE playlist_items (
            playlist_id INTEGER NOT NULL, media_id TEXT NOT NULL, position INTEGER NOT NULL,
            PRIMARY KEY (playlist_id, media_id), UNIQUE (playlist_id, position),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE)""")
        db.execSQL("CREATE TABLE library_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        createQuarantineTable(db)
        db.execSQL("CREATE INDEX media_recent_idx ON media(last_played_at_ms DESC)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) createQuarantineTable(db)
    }

    @Synchronized
    fun recordPlayback(uri: String, title: String, mimeType: String?, positionMs: Long, durationMs: Long) {
        recordPlaybackAt(uri, title, mimeType, positionMs, durationMs, System.currentTimeMillis())
    }

    private fun recordPlaybackAt(
        uri: String,
        title: String,
        mimeType: String?,
        positionMs: Long,
        durationMs: Long,
        lastPlayedAtMs: Long,
    ) {
        if (!isOwnedUri(uri)) return
        val now = System.currentTimeMillis()
        writableDatabase.insertWithOnConflict("media", null, ContentValues().apply {
            put("id", stableId(uri)); put("uri", uri); put("title", title.ifBlank { "Media" })
            put("mime_type", mimeType); put("duration_ms", durationMs.coerceAtLeast(0L))
            put("position_ms", positionMs.coerceAtLeast(0L)); put("added_at_ms", now)
            put("last_played_at_ms", lastPlayedAtMs.coerceAtLeast(0L))
        }, SQLiteDatabase.CONFLICT_IGNORE)
        writableDatabase.update("media", ContentValues().apply {
            put("title", title.ifBlank { "Media" }); put("mime_type", mimeType)
            put("duration_ms", durationMs.coerceAtLeast(0L)); put("position_ms", positionMs.coerceAtLeast(0L))
            put("last_played_at_ms", lastPlayedAtMs.coerceAtLeast(0L))
        }, "uri = ? AND (last_played_at_ms IS NULL OR last_played_at_ms <= ?)",
            arrayOf(uri, lastPlayedAtMs.coerceAtLeast(0L).toString()))
    }

    fun get(uri: String): Media? = readableDatabase.query(
        "media", MEDIA_COLUMNS, "uri = ?", arrayOf(uri), null, null, null, "1",
    ).use { if (it.moveToFirst()) mediaFrom(it) else null }

    fun media(limit: Int = 100): List<Media> = readableDatabase.query(
        "media", MEDIA_COLUMNS, null, null, null, null,
        "COALESCE(last_played_at_ms, added_at_ms) DESC", limit.coerceIn(1, 500).toString(),
    ).use { cursor -> buildList { while (cursor.moveToNext()) add(mediaFrom(cursor)) } }

    /** Clears playback facts only; library membership and files remain untouched. */
    fun clearPlaybackHistory() = writableDatabase.update("media", ContentValues().apply {
        putNull("last_played_at_ms"); put("position_ms", 0L)
    }, null, null)

    /** Removes library membership. ON DELETE CASCADE removes playlist links, never the file. */
    fun removeFromLibrary(mediaId: String) = writableDatabase.delete("media", "id = ?", arrayOf(mediaId)) > 0

    /** Explicit destructive operation: delete the file first, then its library membership. */
    fun deleteFile(media: Media): Boolean {
        val deleted = runCatching {
            if (Uri.parse(media.uri).scheme == "content") context.contentResolver.delete(Uri.parse(media.uri), null, null) > 0
            else File(Uri.parse(media.uri).path ?: return false).delete()
        }.getOrDefault(false)
        if (deleted || !canRead(media.uri)) removeFromLibrary(media.id)
        return deleted
    }

    fun createPlaylist(name: String): Long {
        val clean = name.trim().take(80)
        require(clean.isNotBlank())
        val now = System.currentTimeMillis()
        return writableDatabase.insertOrThrow("playlists", null, ContentValues().apply {
            put("name", clean); put("created_at_ms", now); put("updated_at_ms", now)
        })
    }

    fun renamePlaylist(id: Long, name: String): Boolean {
        val clean = name.trim().take(80); require(clean.isNotBlank())
        return writableDatabase.update("playlists", ContentValues().apply {
            put("name", clean); put("updated_at_ms", System.currentTimeMillis())
        }, "id = ?", arrayOf(id.toString())) > 0
    }

    fun deletePlaylist(id: Long) = writableDatabase.delete("playlists", "id = ?", arrayOf(id.toString())) > 0

    fun playlists(): List<Playlist> = readableDatabase.query(
        "playlists", arrayOf("id", "name", "created_at_ms", "updated_at_ms"),
        null, null, null, null, "name COLLATE NOCASE",
    ).use { c -> buildList { while (c.moveToNext()) add(Playlist(c.getLong(0), c.getString(1), c.getLong(2), c.getLong(3))) } }

    @Synchronized
    fun addToPlaylist(playlistId: Long, mediaId: String) {
        writableDatabase.beginTransaction()
        try {
            val next = writableDatabase.rawQuery(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_items WHERE playlist_id = ?",
                arrayOf(playlistId.toString()),
            ).use { it.moveToFirst(); it.getInt(0) }
            writableDatabase.insertWithOnConflict("playlist_items", null, ContentValues().apply {
                put("playlist_id", playlistId); put("media_id", mediaId); put("position", next)
            }, SQLiteDatabase.CONFLICT_IGNORE)
            touchPlaylist(playlistId)
            writableDatabase.setTransactionSuccessful()
        } finally { writableDatabase.endTransaction() }
    }

    @Synchronized
    fun movePlaylistItem(playlistId: Long, mediaId: String, delta: Int) {
        val ids = playlistMedia(playlistId).map { it.id }.toMutableList()
        val from = ids.indexOf(mediaId); if (from < 0) return
        val to = (from + delta).coerceIn(0, ids.lastIndex); if (from == to) return
        val moved = ids.removeAt(from); ids.add(to, moved)
        writableDatabase.beginTransaction()
        try {
            writableDatabase.delete("playlist_items", "playlist_id = ?", arrayOf(playlistId.toString()))
            ids.forEachIndexed { position, id -> writableDatabase.insertOrThrow("playlist_items", null, ContentValues().apply {
                put("playlist_id", playlistId); put("media_id", id); put("position", position)
            }) }
            touchPlaylist(playlistId); writableDatabase.setTransactionSuccessful()
        } finally { writableDatabase.endTransaction() }
    }

    fun playlistMedia(id: Long): List<Media> = readableDatabase.rawQuery(
        "SELECT ${MEDIA_COLUMNS.joinToString(",") { "m.$it" }} FROM playlist_items p JOIN media m ON m.id=p.media_id WHERE p.playlist_id=? ORDER BY p.position",
        arrayOf(id.toString()),
    ).use { c -> buildList { while (c.moveToNext()) add(mediaFrom(c)) } }

    @Synchronized
    fun removeFromPlaylist(playlistId: Long, mediaId: String): Boolean {
        val removed = writableDatabase.delete(
            "playlist_items", "playlist_id = ? AND media_id = ?",
            arrayOf(playlistId.toString(), mediaId),
        ) > 0
        if (removed) {
            val remaining = playlistMedia(playlistId).map { it.id }
            writableDatabase.beginTransaction()
            try {
                writableDatabase.delete("playlist_items", "playlist_id = ?", arrayOf(playlistId.toString()))
                remaining.forEachIndexed { position, id -> writableDatabase.insertOrThrow("playlist_items", null, ContentValues().apply {
                    put("playlist_id", playlistId); put("media_id", id); put("position", position)
                }) }
                touchPlaylist(playlistId); writableDatabase.setTransactionSuccessful()
            } finally { writableDatabase.endTransaction() }
        }
        return removed
    }

    /** Idempotently discovers completed files which have not been played yet. */
    fun reconcileDownloads(): Int {
        val root = (context.getExternalFilesDir(null) ?: context.filesDir).resolve("classydl-downloads")
        if (!root.exists()) return 0
        var added = 0
        root.walkTopDown().filter { it.isFile && MediaMimeTypes.forFile(it) != "application/octet-stream" }.forEach { file ->
            val uri = FileProvider.getUriForFile(context, FILE_PROVIDER_AUTHORITY, file).toString()
            val values = ContentValues().apply {
                put("id", stableId(uri)); put("uri", uri); put("relative_path", file.relativeTo(root).invariantSeparatorsPath)
                put("title", file.nameWithoutExtension); put("mime_type", MediaMimeTypes.forFile(file))
                put("duration_ms", 0L); put("position_ms", 0L); put("added_at_ms", file.lastModified().coerceAtLeast(1L))
            }
            if (writableDatabase.insertWithOnConflict("media", null, values, SQLiteDatabase.CONFLICT_IGNORE) != -1L) added++
        }
        return added
    }

    fun pruneUnreadable(): Int {
        val missing = media(500).filterNot { canRead(it.uri) }
        missing.forEach { removeFromLibrary(it.id) }
        return missing.size
    }

    private fun canRead(uri: String): Boolean = runCatching {
        context.contentResolver.openFileDescriptor(Uri.parse(uri), "r")?.use { true } ?: false
    }.getOrDefault(false)

    private fun isOwnedUri(uri: String) = Uri.parse(uri).let { it.scheme == "content" && it.authority == FILE_PROVIDER_AUTHORITY }

    private fun touchPlaylist(id: Long) { writableDatabase.update("playlists", ContentValues().apply {
        put("updated_at_ms", System.currentTimeMillis())
    }, "id = ?", arrayOf(id.toString())) }

    private fun mediaFrom(c: android.database.Cursor) = Media(
        c.getString(0), c.getString(1), c.getString(2), c.getString(3), c.getString(4),
        c.getLong(5), c.getLong(6), c.getLong(7), if (c.isNull(8)) null else c.getLong(8),
    )

    /** Transactional import, then readback, then legacy deletion. Safe after interruption. */
    private fun migrateLegacyHistory() {
        val db = writableDatabase
        val prefs = context.getSharedPreferences(LEGACY_PREFS, Context.MODE_PRIVATE)
        if (db.rawQuery("SELECT value FROM library_state WHERE key='legacy_history_v1'", null)
                .use { it.moveToFirst() && it.getString(0) in MIGRATED_STATES }) {
            prefs.edit().remove(LEGACY_KEY).commit()
            return
        }
        val raw = prefs.getString(LEGACY_KEY, null)
        val importedIds = mutableSetOf<String>()
        val quarantinedFingerprints = mutableSetOf<String>()
        db.beginTransaction()
        try {
            if (raw != null) {
                val array = try {
                    JSONArray(raw)
                } catch (_: JSONException) {
                    quarantine(db, raw, "invalid_history_json").also(quarantinedFingerprints::add)
                    null
                }
                if (array != null) for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i)
                    if (item == null) {
                        quarantine(db, array.opt(i)?.toString().orEmpty(), "invalid_history_entry")
                            .also(quarantinedFingerprints::add)
                        continue
                    }
                    val uri = item.optString("uri")
                    if (!isOwnedUri(uri)) {
                        quarantine(db, item.toString(), "invalid_or_unowned_uri")
                            .also(quarantinedFingerprints::add)
                        continue
                    }
                    recordPlaybackAt(
                        uri,
                        item.optString("title", "Media"),
                        item.optString("mimeType").ifBlank { null },
                        item.optLong("positionMs"),
                        item.optLong("durationMs"),
                        item.optLong("lastPlayedAtMs", 0L),
                    )
                    importedIds.add(stableId(uri))
                }
            }
            checkMigrationReadback(db, importedIds, quarantinedFingerprints)
            db.insertWithOnConflict("library_state", null, ContentValues().apply {
                put("key", "legacy_history_v1")
                put("value", if (quarantinedFingerprints.isEmpty()) "done" else "quarantined")
            }, SQLiteDatabase.CONFLICT_REPLACE)
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
        checkMigrationReadback(db, importedIds, quarantinedFingerprints)
        val migrationCommitted = db.rawQuery(
            "SELECT 1 FROM library_state WHERE key = ? AND value IN (?, ?)",
            arrayOf("legacy_history_v1", "done", "quarantined"),
        ).use { it.moveToFirst() }
        if (migrationCommitted) prefs.edit().remove(LEGACY_KEY).commit()
    }

    private fun createQuarantineTable(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE IF NOT EXISTS library_quarantine (
            fingerprint TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL,
            reason TEXT NOT NULL, created_at_ms INTEGER NOT NULL)""")
    }

    private fun quarantine(db: SQLiteDatabase, payload: String, reason: String): String {
        val fingerprint = stableId("$LEGACY_KEY\u0000$reason\u0000$payload")
        db.insertWithOnConflict("library_quarantine", null, ContentValues().apply {
            put("fingerprint", fingerprint); put("source", LEGACY_KEY); put("payload", payload)
            put("reason", reason); put("created_at_ms", System.currentTimeMillis())
        }, SQLiteDatabase.CONFLICT_IGNORE)
        return fingerprint
    }

    private fun checkMigrationReadback(
        db: SQLiteDatabase,
        importedIds: Set<String>,
        quarantineFingerprints: Set<String>,
    ) {
        check(importedIds.all { id ->
            db.rawQuery("SELECT 1 FROM media WHERE id = ?", arrayOf(id)).use { it.moveToFirst() }
        }) { "Legacy media readback failed" }
        check(quarantineFingerprints.all { fingerprint ->
            db.rawQuery("SELECT 1 FROM library_quarantine WHERE fingerprint = ?", arrayOf(fingerprint))
                .use { it.moveToFirst() }
        }) { "Legacy quarantine readback failed" }
    }

    companion object {
        private const val DATABASE_NAME = "media_library.db"
        private const val DATABASE_VERSION = 2
        private const val FILE_PROVIDER_AUTHORITY = "de.classydl.app.fileprovider"
        private const val LEGACY_PREFS = "downloadthat_playback_retention"
        private const val LEGACY_KEY = "history_json"
        private val MIGRATED_STATES = setOf("done", "quarantined")
        private val MEDIA_COLUMNS = arrayOf("id", "uri", "relative_path", "title", "mime_type", "duration_ms", "position_ms", "added_at_ms", "last_played_at_ms")
        fun stableId(uri: String): String = MessageDigest.getInstance("SHA-256")
            .digest(uri.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }
}
