package de.classydl.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.net.Uri
import androidx.core.content.FileProvider
import org.json.JSONArray
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
        db.execSQL("CREATE INDEX media_recent_idx ON media(last_played_at_ms DESC)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    @Synchronized
    fun recordPlayback(uri: String, title: String, mimeType: String?, positionMs: Long, durationMs: Long) {
        if (!isOwnedUri(uri)) return
        val now = System.currentTimeMillis()
        writableDatabase.insertWithOnConflict("media", null, ContentValues().apply {
            put("id", stableId(uri)); put("uri", uri); put("title", title.ifBlank { "Media" })
            put("mime_type", mimeType); put("duration_ms", durationMs.coerceAtLeast(0L))
            put("position_ms", positionMs.coerceAtLeast(0L)); put("added_at_ms", now)
            put("last_played_at_ms", now)
        }, SQLiteDatabase.CONFLICT_IGNORE)
        writableDatabase.update("media", ContentValues().apply {
            put("title", title.ifBlank { "Media" }); put("mime_type", mimeType)
            put("duration_ms", durationMs.coerceAtLeast(0L)); put("position_ms", positionMs.coerceAtLeast(0L))
            put("last_played_at_ms", now)
        }, "uri = ?", arrayOf(uri))
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
        if (db.rawQuery("SELECT value FROM library_state WHERE key='legacy_history_v1'", null)
                .use { it.moveToFirst() && it.getString(0) == "done" }) return
        val prefs = context.getSharedPreferences(LEGACY_PREFS, Context.MODE_PRIVATE)
        val raw = prefs.getString(LEGACY_KEY, null)
        var imported = 0
        db.beginTransaction()
        try {
            if (!raw.isNullOrBlank()) {
                val array = runCatching { JSONArray(raw) }.getOrNull() ?: JSONArray()
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    val uri = item.optString("uri"); if (!isOwnedUri(uri)) continue
                    recordPlayback(uri, item.optString("title", "Media"), item.optString("mimeType").ifBlank { null },
                        item.optLong("positionMs"), item.optLong("durationMs"))
                    imported++
                }
            }
            db.insertWithOnConflict("library_state", null, ContentValues().apply {
                put("key", "legacy_history_v1"); put("value", "done")
            }, SQLiteDatabase.CONFLICT_REPLACE)
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
        val readback = db.rawQuery("SELECT COUNT(*) FROM media", null).use { it.moveToFirst(); it.getInt(0) }
        if (readback >= imported) prefs.edit().remove(LEGACY_KEY).commit()
    }

    companion object {
        private const val DATABASE_NAME = "media_library.db"
        private const val DATABASE_VERSION = 1
        private const val FILE_PROVIDER_AUTHORITY = "de.classydl.app.fileprovider"
        private const val LEGACY_PREFS = "downloadthat_playback_retention"
        private const val LEGACY_KEY = "history_json"
        private val MEDIA_COLUMNS = arrayOf("id", "uri", "relative_path", "title", "mime_type", "duration_ms", "position_ms", "added_at_ms", "last_played_at_ms")
        fun stableId(uri: String): String = MessageDigest.getInstance("SHA-256")
            .digest(uri.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    }
}
