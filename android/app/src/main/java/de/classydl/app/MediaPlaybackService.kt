package de.classydl.app

import android.os.Handler
import android.os.Looper
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService

/**
 * App-wide playback owner.
 *
 * PlayerActivity is only a UI/controller. The actual ExoPlayer and MediaSession
 * live here so audio survives Activity destruction, screen-off and app switches,
 * while Android supplies lock-screen, notification, headset and Bluetooth controls.
 */
class MediaPlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null
    private lateinit var retentionStore: PlaybackRetentionStore
    private val handler = Handler(Looper.getMainLooper())

    private val sleepTimerCheck = object : Runnable {
        override fun run() {
            val deadline = retentionStore.sleepDeadlineMs()
            if (deadline > 0L && System.currentTimeMillis() >= deadline) {
                mediaSession?.player?.pause()
                retentionStore.clearSleepTimer()
            }
            handler.postDelayed(this, 1_000L)
        }
    }

    override fun onCreate() {
        super.onCreate()
        retentionStore = PlaybackRetentionStore(this)

        val audioAttributes = AudioAttributes.Builder()
            .setUsage(C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .build()

        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(audioAttributes, true)
            .setHandleAudioBecomingNoisy(true)
            // Matches PlayerActivity's double-tap seek step so the native
            // controller's rewind/fast-forward glyphs agree with the
            // gesture layer instead of using ExoPlayer's 5s default.
            .setSeekBackIncrementMs(SEEK_STEP_MS)
            .setSeekForwardIncrementMs(SEEK_STEP_MS)
            .build()

        mediaSession = MediaSession.Builder(this, player).build()
        handler.post(sleepTimerCheck)
    }

    override fun onGetSession(
        controllerInfo: MediaSession.ControllerInfo,
    ): MediaSession? = mediaSession

    override fun onDestroy() {
        handler.removeCallbacks(sleepTimerCheck)
        mediaSession?.let { session ->
            session.player.release()
            session.release()
        }
        mediaSession = null
        super.onDestroy()
    }

    companion object {
        private const val SEEK_STEP_MS = 10_000L
    }
}
