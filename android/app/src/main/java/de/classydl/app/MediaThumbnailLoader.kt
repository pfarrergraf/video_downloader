package de.classydl.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.LruCache
import android.widget.ImageView
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.Executors
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/**
 * Generates and caches a representative thumbnail per [MediaLibraryStore.Media]
 * entry — the first video frame, or an audio file's embedded cover art — with
 * no new image-loading dependency (mirrors the LruCache/bounded-executor/
 * view-tag-guard pattern already used by SearchActivity's network thumbnails).
 *
 * One instance per Activity; call [shutdown] from onDestroy.
 */
class MediaThumbnailLoader(private val context: Context) {
    private val memoryCache = object : LruCache<String, Bitmap>(MEMORY_CACHE_BYTES) {
        override fun sizeOf(key: String, value: Bitmap) = value.byteCount
    }
    private val executor = ThreadPoolExecutor(
        2, 2, 30L, TimeUnit.SECONDS, ArrayBlockingQueue(64),
        Executors.defaultThreadFactory(), ThreadPoolExecutor.DiscardOldestPolicy(),
    ).apply { allowCoreThreadTimeOut(true) }
    private val mainHandler = Handler(Looper.getMainLooper())
    private val diskCacheDir: File by lazy {
        File(context.cacheDir, "media_thumbnails").apply { mkdirs() }
    }

    fun load(media: MediaLibraryStore.Media, into: ImageView, placeholder: Int) {
        into.tag = media.id
        memoryCache.get(media.id)?.let { into.setImageBitmap(it); return }
        into.setImageResource(placeholder)
        executor.execute {
            val bitmap = runCatching { loadOrGenerate(media) }.getOrNull()
            if (bitmap != null) memoryCache.put(media.id, bitmap)
            mainHandler.post {
                if (into.tag == media.id && bitmap != null) into.setImageBitmap(bitmap)
            }
        }
    }

    fun cancel(into: ImageView) {
        into.tag = null
    }

    fun shutdown() {
        executor.shutdownNow()
    }

    private fun loadOrGenerate(media: MediaLibraryStore.Media): Bitmap? {
        val diskFile = File(diskCacheDir, "${media.id}.jpg")
        if (diskFile.exists()) {
            BitmapFactory.decodeFile(diskFile.path)?.let { return it }
        }
        val bitmap = generate(media) ?: return null
        runCatching {
            FileOutputStream(diskFile).use { bitmap.compress(Bitmap.CompressFormat.JPEG, 85, it) }
        }
        return bitmap
    }

    private fun generate(media: MediaLibraryStore.Media): Bitmap? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, Uri.parse(media.uri))
            if (media.mimeType?.startsWith("video/") == true) {
                retriever.getFrameAtTime(0L, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
            } else {
                retriever.embeddedPicture?.let { BitmapFactory.decodeByteArray(it, 0, it.size) }
            }
        } catch (_: Exception) {
            null
        } finally {
            runCatching { retriever.release() }
        }
    }

    companion object {
        private const val MEMORY_CACHE_BYTES = 16 * 1024 * 1024
    }
}
