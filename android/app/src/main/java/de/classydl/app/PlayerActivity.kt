package de.classydl.app

import android.content.ComponentName
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import androidx.media3.ui.PlayerView
import com.google.common.util.concurrent.ListenableFuture

/**
 * Native playback surface for both DownloadThat-owned files and external
 * content:// URIs opened from Android file managers or other apps.
 */
class PlayerActivity : AppCompatActivity() {
    private lateinit var playerView: PlayerView
    private lateinit var titleView: TextView
    private lateinit var controllerFuture: ListenableFuture<MediaController>
    private var controller: MediaController? = null
    private var pendingUri: Uri? = null
    private var pendingMimeType: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_player)

        playerView = findViewById(R.id.player_view)
        titleView = findViewById(R.id.player_title)
        findViewById<View>(R.id.player_back).setOnClickListener { finish() }

        consumeIntent(intent)
        connectController()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        consumeIntent(intent)
        controller?.let(::playPendingUri)
    }

    override fun onDestroy() {
        playerView.player = null
        controller?.release()
        controller = null
        if (::controllerFuture.isInitialized && !controllerFuture.isDone) {
            controllerFuture.cancel(true)
        }
        super.onDestroy()
    }

    private fun connectController() {
        val token = SessionToken(this, ComponentName(this, MediaPlaybackService::class.java))
        controllerFuture = MediaController.Builder(this, token).buildAsync()
        controllerFuture.addListener(
            {
                if (isFinishing || isDestroyed || controllerFuture.isCancelled) return@addListener
                runCatching { controllerFuture.get() }
                    .onSuccess { mediaController ->
                        controller = mediaController
                        playerView.player = mediaController
                        playPendingUri(mediaController)
                    }
                    .onFailure { showPlaybackError() }
            },
            ContextCompat.getMainExecutor(this),
        )
    }

    private fun consumeIntent(intent: Intent?) {
        if (intent?.action != Intent.ACTION_VIEW && intent?.action != ACTION_PLAY_INTERNAL) {
            showPlaybackError()
            return
        }

        val uri = intent.data
        if (uri == null || (uri.scheme != "content" && uri.scheme != "file")) {
            showPlaybackError()
            return
        }

        pendingUri = uri
        pendingMimeType = intent.type ?: contentResolver.getType(uri)
        titleView.text = displayName(uri) ?: getString(R.string.player_unknown_title)
    }

    private fun playPendingUri(mediaController: MediaController) {
        val uri = pendingUri ?: return
        val mediaId = uri.toString()

        // Rotation/recreation or reopening the same URI must not reset playback.
        if (mediaController.currentMediaItem?.mediaId == mediaId) return

        val metadata = MediaMetadata.Builder()
            .setTitle(displayName(uri) ?: getString(R.string.player_unknown_title))
            .build()
        val itemBuilder = MediaItem.Builder()
            .setUri(uri)
            .setMediaId(mediaId)
            .setMediaMetadata(metadata)
        pendingMimeType?.takeIf { it.isNotBlank() }?.let(itemBuilder::setMimeType)

        mediaController.setMediaItem(itemBuilder.build())
        mediaController.prepare()
        mediaController.play()
    }

    private fun displayName(uri: Uri): String? {
        if (uri.scheme != "content") return uri.lastPathSegment
        var cursor: Cursor? = null
        return try {
            cursor = contentResolver.query(
                uri,
                arrayOf(OpenableColumns.DISPLAY_NAME),
                null,
                null,
                null,
            )
            if (cursor != null && cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) cursor.getString(index) else uri.lastPathSegment
            } else {
                uri.lastPathSegment
            }
        } catch (_: Exception) {
            uri.lastPathSegment
        } finally {
            cursor?.close()
        }
    }

    private fun showPlaybackError() {
        titleView.text = getString(R.string.player_could_not_open)
    }

    companion object {
        const val ACTION_PLAY_INTERNAL = "de.classydl.app.action.PLAY_INTERNAL"
    }
}
