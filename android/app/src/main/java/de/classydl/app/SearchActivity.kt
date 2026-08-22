package de.classydl.app

import android.graphics.BitmapFactory
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.chaquo.python.Python
import org.json.JSONObject
import java.net.URI
import kotlin.concurrent.thread

/**
 * Native discovery surface: query -> four compact results -> Video/Audio queue.
 *
 * Discovery is metadata-only. Every actual download is posted to the existing
 * authenticated /api/queue endpoint, so free-tier limits and Pro entitlements
 * are exactly the same as for links entered in the main WebView UI.
 */
class SearchActivity : AppCompatActivity() {
    private lateinit var queryInput: android.widget.EditText
    private lateinit var searchButton: Button
    private lateinit var statusView: TextView
    private lateinit var resultsContainer: LinearLayout
    @Volatile private var searchGeneration = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_search)

        findViewById<ViewGroup>(R.id.search_back).setOnClickListener { finish() }
        queryInput = findViewById(R.id.search_query)
        searchButton = findViewById(R.id.search_button)
        statusView = findViewById(R.id.search_status)
        resultsContainer = findViewById(R.id.search_results)

        // Search can be the first native screen opened in a process. Starting
        // DownloadService guarantees both Chaquopy and the queue API are alive,
        // and keeps a newly queued result protected when the user backgrounds.
        ContextCompat.startForegroundService(this, android.content.Intent(this, DownloadService::class.java))

        searchButton.setOnClickListener { runSearch() }
        queryInput.setOnEditorActionListener { _, _, _ ->
            runSearch()
            true
        }
    }

    private fun runSearch() {
        val requestGeneration = ++searchGeneration
        val query = queryInput.text?.toString()?.trim().orEmpty()
        if (query.isBlank()) {
            statusView.setText(R.string.search_enter_query)
            return
        }
        searchButton.isEnabled = false
        resultsContainer.removeAllViews()
        statusView.setText(R.string.search_searching)

        thread(name = "downloadthat-media-search", isDaemon = true) {
            try {
                for (attempt in 0 until 60) {
                    if (Python.isStarted()) break
                    Thread.sleep(100L)
                }
                if (!Python.isStarted()) error("Python runtime did not start")
                val json = Python.getInstance()
                    .getModule("video_downloader.media_search")
                    .callAttr("search_youtube_json", query, 4)
                    .toString()
                val root = JSONObject(json)
                val array = root.optJSONArray("results")
                val results = buildList {
                    if (array != null) {
                        for (i in 0 until array.length()) {
                            val item = array.optJSONObject(i) ?: continue
                            add(
                                SearchResult(
                                    title = item.optString("title", getString(R.string.player_unknown_title)),
                                    url = item.optString("url"),
                                    thumbnail = item.optString("thumbnail"),
                                    uploader = item.optString("uploader"),
                                    durationSeconds = if (item.isNull("duration")) null else item.optInt("duration"),
                                ),
                            )
                        }
                    }
                }
                runOnUiThread {
                    if (!isCurrentUi(requestGeneration)) return@runOnUiThread
                    searchButton.isEnabled = true
                    if (results.isEmpty()) {
                        statusView.setText(R.string.search_no_results)
                    } else {
                        statusView.text = resources.getQuantityString(
                            R.plurals.search_results_count,
                            results.size,
                            results.size,
                        )
                        renderResults(results, requestGeneration)
                    }
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    if (!isCurrentUi(requestGeneration)) return@runOnUiThread
                    searchButton.isEnabled = true
                    statusView.text = getString(R.string.search_failed, error.message ?: "unknown error")
                }
            }
        }
    }

    override fun onDestroy() {
        searchGeneration++
        super.onDestroy()
    }

    private fun isCurrentUi(requestGeneration: Int): Boolean =
        requestGeneration == searchGeneration && !isFinishing && !isDestroyed

    private fun renderResults(results: List<SearchResult>, requestGeneration: Int) {
        resultsContainer.removeAllViews()
        results.forEach { result ->
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(12), dp(12), dp(12), dp(12))
                background = ContextCompat.getDrawable(this@SearchActivity, R.drawable.bg_media_card)
            }
            val cardParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { bottomMargin = dp(12) }
            resultsContainer.addView(card, cardParams)

            val top = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.TOP
            }
            card.addView(top)

            val thumbnail = ImageView(this).apply {
                scaleType = ImageView.ScaleType.CENTER_CROP
                contentDescription = null
                setBackgroundColor(0xFF1A1930.toInt())
            }
            top.addView(thumbnail, LinearLayout.LayoutParams(dp(128), dp(72)))
            loadThumbnail(result.thumbnail, thumbnail, requestGeneration)

            val meta = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(12), 0, 0, 0)
            }
            top.addView(
                meta,
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f),
            )
            meta.addView(TextView(this).apply {
                text = result.title
                setTextColor(0xFFF3F1FB.toInt())
                textSize = 16f
                setTypeface(typeface, Typeface.BOLD)
                maxLines = 3
            })
            val detail = listOfNotNull(
                result.uploader.takeIf { it.isNotBlank() },
                formatDuration(result.durationSeconds),
            ).joinToString(" · ")
            if (detail.isNotBlank()) {
                meta.addView(TextView(this).apply {
                    text = detail
                    setTextColor(0xFFA5A0C0.toInt())
                    textSize = 13f
                })
            }

            val actions = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, dp(10), 0, 0)
            }
            card.addView(actions)
            val video = Button(this).apply {
                setText(R.string.search_download_video)
                setOnClickListener { enqueue(result, audioOnly = false, this, requestGeneration) }
            }
            val audio = Button(this).apply {
                setText(R.string.search_download_audio)
                setOnClickListener { enqueue(result, audioOnly = true, this, requestGeneration) }
            }
            actions.addView(video, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            actions.addView(audio, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                marginStart = dp(8)
            })
        }
    }

    private fun enqueue(result: SearchResult, audioOnly: Boolean, button: Button, requestGeneration: Int) {
        if (result.url.isBlank()) return
        button.isEnabled = false
        statusView.setText(R.string.search_queueing)
        thread(name = "downloadthat-search-queue", isDaemon = true) {
            val queueResult = runCatching { LocalApiClient.enqueue(this, result.url, audioOnly) }
                .getOrElse { LocalApiClient.QueueResult(false, error = it.message) }
            runOnUiThread {
                if (!isCurrentUi(requestGeneration)) return@runOnUiThread
                button.isEnabled = true
                if (queueResult.ok) {
                    statusView.text = getString(R.string.search_queued, result.title)
                    Toast.makeText(this, R.string.search_download_started, Toast.LENGTH_SHORT).show()
                } else {
                    statusView.text = queueResult.error ?: getString(R.string.search_queue_failed)
                }
            }
        }
    }

    private fun loadThumbnail(url: String, imageView: ImageView, requestGeneration: Int) {
        val parsed = runCatching { URI(url).toURL() }.getOrNull() ?: return
        if (parsed.protocol != "https" || parsed.host !in setOf("i.ytimg.com", "img.youtube.com")) return
        thread(name = "downloadthat-thumbnail", isDaemon = true) {
            val bitmap = runCatching {
                val connection = parsed.openConnection().apply {
                    connectTimeout = 4_000
                    readTimeout = 6_000
                }
                connection.getInputStream().use { stream -> BitmapFactory.decodeStream(stream) }
            }.getOrNull() ?: return@thread
            runOnUiThread {
                if (isCurrentUi(requestGeneration)) imageView.setImageBitmap(bitmap)
            }
        }
    }

    private fun formatDuration(seconds: Int?): String? {
        if (seconds == null || seconds <= 0) return null
        val hours = seconds / 3600
        val minutes = (seconds % 3600) / 60
        val secs = seconds % 60
        return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, secs)
        else "%d:%02d".format(minutes, secs)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private data class SearchResult(
        val title: String,
        val url: String,
        val thumbnail: String,
        val uploader: String,
        val durationSeconds: Int?,
    )
}
