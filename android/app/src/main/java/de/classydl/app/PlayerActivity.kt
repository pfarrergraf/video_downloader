package de.classydl.app

import android.app.PictureInPictureParams
import android.content.ComponentName
import android.content.Intent
import android.content.res.Configuration
import android.database.Cursor
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.provider.Settings
import android.util.Rational
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import androidx.media3.ui.PlayerView
import com.google.common.util.concurrent.ListenableFuture
import org.json.JSONArray

/**
 * Native playback surface for both DownloadThat-owned files and external
 * content:// URIs opened from Android file managers or other apps.
 *
 * Retention layer: local resume points/recent history, playback speed,
 * service-level sleep timer, a recent-items playlist and video PiP.
 */
class PlayerActivity : AppCompatActivity() {
    private lateinit var playerView: PlayerView
    private lateinit var titleView: TextView
    private lateinit var speedButton: Button
    private lateinit var sleepButton: Button
    private lateinit var seekFeedback: TextView
    private lateinit var topChrome: View
    private lateinit var retentionActions: View
    private lateinit var retentionStore: PlaybackRetentionStore
    private lateinit var libraryStore: MediaLibraryStore
    private lateinit var controllerFuture: ListenableFuture<MediaController>
    private var controller: MediaController? = null
    private var pendingUri: Uri? = null
    private var pendingMimeType: String? = null
    private var pendingPlaylist: List<PlaylistEntry> = emptyList()
    private var pendingShuffle = false
    private var pendingRepeatMode = Player.REPEAT_MODE_OFF
    private var showCurrentSession = false
    private var controlsVisible = true
    private var videoZoom = 1f
    private val handler = Handler(Looper.getMainLooper())

    private val checkpoint = object : Runnable {
        override fun run() {
            saveCurrentPosition()
            updateSleepButton()
            handler.postDelayed(this, CHECKPOINT_MS)
        }
    }

    private val playerListener = object : Player.Listener {
        override fun onPlaybackStateChanged(playbackState: Int) {
            if (playbackState == Player.STATE_ENDED) saveCurrentPosition()
            updatePictureInPictureParams()
        }

        override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
            showPlaybackError()
        }

        override fun onIsPlayingChanged(isPlaying: Boolean) {
            updatePictureInPictureParams()
        }

        override fun onVolumeChanged(volume: Float) {
            // Report the value acknowledged by the service-owned player, not
            // merely the requested gesture target.
            showBubble("🔊 ${PlayerGestureMath.percentFromUnitValue(volume)}%")
        }

        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            val title = mediaItem?.mediaMetadata?.title?.toString()
            if (!title.isNullOrBlank()) titleView.text = title
            pendingMimeType = mediaItem?.localConfiguration?.mimeType ?: pendingMimeType
            updatePictureInPictureParams()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_player)

        retentionStore = PlaybackRetentionStore(this)
        libraryStore = MediaLibraryStore(this)
        playerView = findViewById(R.id.player_view)
        titleView = findViewById(R.id.player_title)
        speedButton = findViewById(R.id.player_speed)
        sleepButton = findViewById(R.id.player_sleep)
        seekFeedback = findViewById(R.id.player_seek_feedback)
        topChrome = findViewById(R.id.player_top_chrome)
        retentionActions = findViewById(R.id.player_retention_actions)

        findViewById<View>(R.id.player_back).setOnClickListener { finish() }
        findViewById<Button>(R.id.player_history).setOnClickListener {
            startActivity(Intent(this, MediaHistoryActivity::class.java))
        }
        findViewById<Button>(R.id.player_search).apply {
            visibility = if (BuildConfig.PLAY_POLICY_RESTRICTED) View.GONE else View.VISIBLE
            setOnClickListener { startActivity(Intent(this@PlayerActivity, SearchActivity::class.java)) }
        }
        speedButton.setOnClickListener { cyclePlaybackSpeed() }
        sleepButton.setOnClickListener { cycleSleepTimer() }
        setupGestures()

        consumeIntent(intent)
        updateSpeedButton(retentionStore.playbackSpeed())
        updateSleepButton()
        connectController()
        handler.postDelayed(checkpoint, CHECKPOINT_MS)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        saveCurrentPosition()
        setIntent(intent)
        consumeIntent(intent)
        controller?.let(::playPendingMedia)
    }

    override fun onStop() {
        saveCurrentPosition()
        super.onStop()
    }

    override fun onDestroy() {
        handler.removeCallbacks(checkpoint)
        saveCurrentPosition()
        playerView.player = null
        controller?.removeListener(playerListener)
        controller?.release()
        controller = null
        libraryStore.close()
        if (::controllerFuture.isInitialized && !controllerFuture.isDone) {
            controllerFuture.cancel(true)
        }
        super.onDestroy()
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (Build.VERSION.SDK_INT in 26..30 && isCurrentVideo() && controller?.isPlaying == true) {
            runCatching { enterPictureInPictureMode(buildPictureInPictureParams(autoEnter = false)) }
        }
    }

    override fun onPictureInPictureModeChanged(
        isInPictureInPictureMode: Boolean,
        newConfig: Configuration,
    ) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        val visibility = if (isInPictureInPictureMode) View.GONE else View.VISIBLE
        topChrome.visibility = visibility
        retentionActions.visibility = visibility
        playerView.useController = !isInPictureInPictureMode
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
                        mediaController.addListener(playerListener)
                        mediaController.setPlaybackSpeed(retentionStore.playbackSpeed())
                        playerView.player = mediaController
                        playPendingMedia(mediaController)
                        updatePictureInPictureParams()
                    }
                    .onFailure { showPlaybackError() }
            },
            ContextCompat.getMainExecutor(this),
        )
    }

    private fun consumeIntent(intent: Intent?) {
        pendingUri = null
        pendingMimeType = null
        pendingPlaylist = emptyList()
        showCurrentSession = intent?.action == ACTION_SHOW_CURRENT
        pendingShuffle = intent?.getBooleanExtra(EXTRA_SHUFFLE, false) ?: false
        pendingRepeatMode = intent?.getIntExtra(EXTRA_REPEAT_MODE, Player.REPEAT_MODE_OFF) ?: Player.REPEAT_MODE_OFF
        if (showCurrentSession) return
        if (intent?.action != Intent.ACTION_VIEW && intent?.action != ACTION_PLAY_INTERNAL) {
            showPlaybackError()
            return
        }

        val uri = intent.data
        if (uri == null || !isLocalPlaybackUri(uri)) {
            showPlaybackError()
            return
        }

        if (
            uri.scheme == "content" &&
            intent.flags and Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION != 0
        ) {
            runCatching {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }

        pendingUri = uri
        pendingMimeType = intent.type ?: contentResolver.getType(uri)
        val playlist = parsePlaylist(intent.getStringExtra(EXTRA_PLAYLIST_JSON))
        pendingPlaylist = playlist.entries
        if (playlist.rejectedEntries > 0) {
            Toast.makeText(this, R.string.player_playlist_items_skipped, Toast.LENGTH_SHORT).show()
        }
        titleView.text = pendingPlaylist.firstOrNull()?.title
            ?: displayName(uri)
            ?: getString(R.string.player_unknown_title)
    }

    private fun playPendingMedia(mediaController: MediaController) {
        if (showCurrentSession) {
            showCurrentMedia(mediaController)
            return
        }
        val uri = pendingUri ?: return
        // Applied unconditionally, ahead of the same-item early-returns below,
        // so a repeat/shuffle-only change (same playlist, different mode)
        // still takes effect on a re-delivered intent (onNewIntent).
        mediaController.shuffleModeEnabled = pendingShuffle
        mediaController.repeatMode = pendingRepeatMode
        val resumeMs = libraryStore.get(uri.toString())
            ?.takeIf { it.isMeaningfulResume }
            ?.positionMs
            ?: 0L

        if (pendingPlaylist.isNotEmpty()) {
            val items = pendingPlaylist.map(::mediaItemForPlaylistEntry)
            if (mediaController.currentMediaItem?.mediaId == items.firstOrNull()?.mediaId &&
                mediaController.mediaItemCount == items.size
            ) {
                return
            }
            mediaController.setMediaItems(items, 0, resumeMs)
            mediaController.prepare()
            mediaController.play()
            return
        }

        val mediaId = uri.toString()
        if (mediaController.currentMediaItem?.mediaId == mediaId) return

        val title = displayName(uri) ?: getString(R.string.player_unknown_title)
        val metadata = MediaMetadata.Builder().setTitle(title).build()
        val itemBuilder = MediaItem.Builder()
            .setUri(uri)
            .setMediaId(mediaId)
            .setMediaMetadata(metadata)
        pendingMimeType?.takeIf { it.isNotBlank() }?.let(itemBuilder::setMimeType)

        mediaController.setMediaItem(itemBuilder.build(), resumeMs)
        mediaController.prepare()
        mediaController.play()
    }

    /** Rebinds the UI to service-owned playback without replacing or seeking it. */
    private fun showCurrentMedia(mediaController: MediaController) {
        val item = mediaController.currentMediaItem ?: run {
            showPlaybackError()
            return
        }
        pendingMimeType = item.localConfiguration?.mimeType
        titleView.text = item.mediaMetadata.title?.toString()
            ?.takeIf { it.isNotBlank() }
            ?: displayName(Uri.parse(item.mediaId))
            ?: getString(R.string.player_unknown_title)
        updatePictureInPictureParams()
    }

    private fun saveCurrentPosition() {
        val mediaController = controller ?: return
        val item = mediaController.currentMediaItem ?: return
        val uri = item.mediaId.takeIf { it.isNotBlank() } ?: return
        if (!retentionStore.isOwnedDownloadUri(uri)) return
        val title = item.mediaMetadata.title?.toString()
            ?.takeIf { it.isNotBlank() }
            ?: titleView.text?.toString().orEmpty()
        val duration = mediaController.duration.takeIf { it != C.TIME_UNSET && it > 0L } ?: 0L
        libraryStore.recordPlayback(
            uri = uri,
            title = title,
            mimeType = item.localConfiguration?.mimeType ?: pendingMimeType,
            positionMs = mediaController.currentPosition.coerceAtLeast(0L),
            durationMs = duration,
        )
    }

    private fun cyclePlaybackSpeed() {
        val mediaController = controller ?: return
        val current = mediaController.playbackParameters.speed
        val index = SPEEDS.indexOfFirst { kotlin.math.abs(it - current) < 0.01f }
        val next = SPEEDS[(if (index < 0) 0 else index + 1) % SPEEDS.size]
        mediaController.setPlaybackSpeed(next)
        retentionStore.setPlaybackSpeed(next)
        updateSpeedButton(next)
    }

    private fun updateSpeedButton(speed: Float) {
        speedButton.text = getString(R.string.player_speed_value, formatSpeed(speed))
    }

    private fun cycleSleepTimer() {
        val remaining = retentionStore.sleepMinutesRemaining()
        val next = when {
            remaining <= 0 -> 15
            remaining <= 15 -> 30
            remaining <= 30 -> 60
            else -> 0
        }
        retentionStore.setSleepTimerMinutes(next)
        updateSleepButton()
    }

    private fun updateSleepButton() {
        val remaining = retentionStore.sleepMinutesRemaining()
        sleepButton.text = if (remaining > 0) {
            getString(R.string.player_sleep_value, remaining)
        } else {
            getString(R.string.player_sleep_off)
        }
    }

    /**
     * VLC-style touch controls layered directly on the video surface:
     * pinch to zoom in/out, double-tap the left/right third to skip
     * back/forward 10s, double-tap the middle third to play/pause, a
     * one-finger vertical drag on the right half for volume and the left
     * half for screen brightness, and a single tap anywhere to toggle the
     * chrome. Media3's own tap-to-toggle handling is bypassed once this
     * listener is attached (a view keeps only one OnTouchListener), so
     * controller visibility is tracked here instead.
     */
    @OptIn(UnstableApi::class)
    private fun setupGestures() {
        var gestureStartVolumePercent = MAX_PERCENT
        var gestureStartBrightnessPercent = MAX_PERCENT / 2
        var scaleGestureInProgress = false

        val scaleDetector = ScaleGestureDetector(
            this,
            object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
                override fun onScaleBegin(detector: ScaleGestureDetector): Boolean {
                    scaleGestureInProgress = true
                    return true
                }

                override fun onScale(detector: ScaleGestureDetector): Boolean {
                    videoZoom = (videoZoom * detector.scaleFactor).coerceIn(1f, 3f)
                    playerView.videoSurfaceView?.let {
                        it.scaleX = videoZoom
                        it.scaleY = videoZoom
                    }
                    return true
                }

                override fun onScaleEnd(detector: ScaleGestureDetector) {
                    scaleGestureInProgress = false
                }
            },
        )

        val gestureDetector = GestureDetector(
            this,
            object : GestureDetector.SimpleOnGestureListener() {
                override fun onDown(e: MotionEvent): Boolean = true

                override fun onSingleTapConfirmed(e: MotionEvent): Boolean {
                    controlsVisible = !controlsVisible
                    if (controlsVisible) playerView.showController() else playerView.hideController()
                    return true
                }

                override fun onDoubleTap(e: MotionEvent): Boolean {
                    val mediaController = controller ?: return false
                    val width = playerView.width
                    if (width <= 0) return false
                    when {
                        e.x < width / 3f -> seekBy(mediaController, -SEEK_STEP_MS, "-10s")
                        e.x > width * 2f / 3f -> seekBy(mediaController, SEEK_STEP_MS, "+10s")
                        else -> if (mediaController.isPlaying) mediaController.pause() else mediaController.play()
                    }
                    return true
                }

                override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
                    // Ignore a second finger (already owned by scaleDetector) and
                    // drags that are mostly horizontal, so this only fires for a
                    // deliberate one-finger vertical swipe.
                    if (e1 == null || e2.pointerCount > 1 || scaleGestureInProgress) return false
                    val totalX = e2.x - e1.x
                    val totalY = e1.y - e2.y
                    if (kotlin.math.abs(totalY) <= kotlin.math.abs(totalX)) return false
                    val width = playerView.width
                    val height = playerView.height
                    if (width <= 0 || height <= 0) return false
                    // Use the full distance from ACTION_DOWN rather than each tiny
                    // MotionEvent delta. Otherwise sub-percent deltas get rounded
                    // away independently and a slow swipe can appear to do nothing.
                    if (e1.x < width / 2f) {
                        setBrightnessPercent(
                            PlayerGestureMath.percentFromVerticalDrag(
                                gestureStartBrightnessPercent,
                                e1.y,
                                e2.y,
                                height,
                                MIN_BRIGHTNESS_PERCENT,
                            ),
                        )
                    } else {
                        setVolumePercent(
                            PlayerGestureMath.percentFromVerticalDrag(
                                gestureStartVolumePercent,
                                e1.y,
                                e2.y,
                                height,
                                MIN_VOLUME_PERCENT,
                            ),
                        )
                    }
                    return true
                }
            },
        )

        playerView.setOnTouchListener { view, event ->
            if (event.actionMasked == MotionEvent.ACTION_DOWN) {
                gestureStartVolumePercent = PlayerGestureMath.percentFromUnitValue(controller?.volume ?: 1f)
                gestureStartBrightnessPercent = PlayerGestureMath.percentFromUnitValue(currentBrightness())
            }
            scaleDetector.onTouchEvent(event)
            gestureDetector.onTouchEvent(event)
            if (event.actionMasked == MotionEvent.ACTION_UP) view.performClick()
            true
        }
    }

    private fun seekBy(mediaController: MediaController, deltaMs: Long, label: String) {
        val duration = mediaController.duration.takeIf { it != C.TIME_UNSET } ?: Long.MAX_VALUE
        mediaController.seekTo((mediaController.currentPosition + deltaMs).coerceIn(0L, duration))
        showBubble(label)
    }

    /**
     * App-player gain, deliberately independent of Android's coarse device
     * volume indexes. Media3 exposes a continuous 0..1 value, so the gesture
     * can offer real 1% steps even on devices whose STREAM_MUSIC has only
     * around 15 hardware volume levels.
     */
    private fun setVolumePercent(percent: Int) {
        val mediaController = controller ?: return
        if (!mediaController.isCommandAvailable(Player.COMMAND_SET_VOLUME)) return
        val target = percent.coerceIn(MIN_VOLUME_PERCENT, MAX_PERCENT)
        mediaController.volume = PlayerGestureMath.unitValueFromPercent(target, MIN_VOLUME_PERCENT)
    }

    /**
     * Per-window brightness override only — reverts automatically when this
     * Activity closes and never touches system brightness, so it needs no
     * WRITE_SETTINGS permission (a special access this app does not request;
     * see the Android permission guardrail in CLAUDE.md).
     */
    private fun setBrightnessPercent(percent: Int) {
        val targetPercent = percent.coerceIn(MIN_BRIGHTNESS_PERCENT, MAX_PERCENT)
        val params = window.attributes
        params.screenBrightness = PlayerGestureMath.unitValueFromPercent(targetPercent, MIN_BRIGHTNESS_PERCENT)
        window.attributes = params
        showBubble("☀️ ${PlayerGestureMath.percentFromUnitValue(window.attributes.screenBrightness)}%")
    }

    private fun currentBrightness(): Float =
        window.attributes.screenBrightness.takeIf { it >= 0f } ?: systemBrightnessFraction()

    private fun systemBrightnessFraction(): Float = runCatching {
        Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS) / 255f
    }.getOrDefault(0.5f)

    private fun showBubble(text: String) {
        seekFeedback.text = text
        seekFeedback.animate().cancel()
        seekFeedback.alpha = 1f
        seekFeedback.visibility = View.VISIBLE
        seekFeedback.animate()
            .alpha(0f)
            .setStartDelay(400)
            .setDuration(250)
            .withEndAction { seekFeedback.visibility = View.INVISIBLE }
            .start()
    }

    private fun updatePictureInPictureParams() {
        if (Build.VERSION.SDK_INT < 26 || !isCurrentVideo()) return
        setPictureInPictureParams(buildPictureInPictureParams(autoEnter = controller?.isPlaying == true))
    }

    private fun buildPictureInPictureParams(autoEnter: Boolean): PictureInPictureParams {
        val builder = PictureInPictureParams.Builder().setAspectRatio(Rational(16, 9))
        if (Build.VERSION.SDK_INT >= 31) builder.setAutoEnterEnabled(autoEnter)
        return builder.build()
    }

    private fun isCurrentVideo(): Boolean {
        val mime = controller?.currentMediaItem?.localConfiguration?.mimeType ?: pendingMimeType
        return mime?.startsWith("video/") == true
    }

    private fun mediaItemForPlaylistEntry(entry: PlaylistEntry): MediaItem {
        val builder = MediaItem.Builder()
            .setUri(Uri.parse(entry.uri))
            .setMediaId(entry.uri)
            .setMediaMetadata(MediaMetadata.Builder().setTitle(entry.title).build())
        entry.mimeType?.takeIf { it.isNotBlank() }?.let(builder::setMimeType)
        return builder.build()
    }

    private fun parsePlaylist(raw: String?): PlaylistParseResult {
        if (raw.isNullOrBlank()) return PlaylistParseResult(emptyList(), 0)
        return runCatching {
            val array = JSONArray(raw)
            var rejectedEntries = 0
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    val uri = item.optString("uri")
                    if (uri.isBlank() || !isLocalPlaybackUri(Uri.parse(uri))) {
                        rejectedEntries++
                        continue
                    }
                    add(
                        PlaylistEntry(
                            uri = uri,
                            title = item.optString("title", getString(R.string.player_unknown_title)),
                            mimeType = item.optString("mimeType").takeIf { it.isNotBlank() },
                        ),
                    )
                }
            }.let { PlaylistParseResult(it, rejectedEntries) }
        }.getOrDefault(PlaylistParseResult(emptyList(), 0))
    }

    /** The native player never receives network streams or embedded web media. */
    private fun isLocalPlaybackUri(uri: Uri): Boolean = uri.scheme in LOCAL_URI_SCHEMES

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

    private fun formatSpeed(speed: Float): String = if (speed % 1f == 0f) {
        "${speed.toInt()}x"
    } else {
        "${"%.2f".format(speed).trimEnd('0')}x"
    }

    private data class PlaylistEntry(val uri: String, val title: String, val mimeType: String?)

    private data class PlaylistParseResult(
        val entries: List<PlaylistEntry>,
        val rejectedEntries: Int,
    )

    companion object {
        const val ACTION_PLAY_INTERNAL = "de.classydl.app.action.PLAY_INTERNAL"
        const val ACTION_SHOW_CURRENT = "de.classydl.app.action.SHOW_CURRENT_PLAYBACK"
        const val EXTRA_PLAYLIST_JSON = "de.classydl.app.extra.PLAYLIST_JSON"
        const val EXTRA_SHUFFLE = "de.classydl.app.extra.SHUFFLE"
        const val EXTRA_REPEAT_MODE = "de.classydl.app.extra.REPEAT_MODE"
        private const val CHECKPOINT_MS = 5_000L
        private const val SEEK_STEP_MS = 10_000L
        private const val MIN_VOLUME_PERCENT = 0
        private const val MIN_BRIGHTNESS_PERCENT = 1
        private const val MAX_PERCENT = 100
        private val LOCAL_URI_SCHEMES = setOf("content", "file")
        private val SPEEDS = listOf(1.0f, 1.25f, 1.5f, 2.0f, 0.75f)
    }
}
