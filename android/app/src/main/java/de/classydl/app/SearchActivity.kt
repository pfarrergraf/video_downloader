package de.classydl.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.LruCache
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.chaquo.python.Python
import org.json.JSONObject
import java.net.URI
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

/** Metadata-only native discovery with stable, bounded result snapshots. */
class SearchActivity : AppCompatActivity() {
    private lateinit var queryInput: android.widget.EditText
    private lateinit var searchButton: Button
    private lateinit var moreButton: Button
    private lateinit var statusView: TextView
    private lateinit var adapter: SearchAdapter
    private val searchExecutor = Executors.newSingleThreadExecutor()
    private val thumbnailExecutor = Executors.newFixedThreadPool(3)
    private val thumbnailCache = object : LruCache<String, Bitmap>(12 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.byteCount
    }
    private val generation = AtomicInteger()
    private var nextCursor: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_search)
        // Search may be opened from an external PlayerActivity before MainActivity.
        // This starts only the HTTP/Python runtime; a transfer foreground service
        // is acquired later by the shared enqueue coordinator.
        ServerRuntime.ensureStarted(applicationContext, null)
        findViewById<ViewGroup>(R.id.search_back).setOnClickListener { finish() }
        queryInput = findViewById(R.id.search_query)
        searchButton = findViewById(R.id.search_button)
        moreButton = findViewById(R.id.search_more)
        statusView = findViewById(R.id.search_status)
        adapter = SearchAdapter(::enqueue, ::loadThumbnail)
        findViewById<RecyclerView>(R.id.search_results).apply {
            layoutManager = LinearLayoutManager(this@SearchActivity)
            adapter = this@SearchActivity.adapter
        }
        searchButton.setOnClickListener { startSearch() }
        moreButton.setOnClickListener { loadMore() }
        queryInput.setOnEditorActionListener { _, _, _ -> startSearch(); true }
    }

    private fun startSearch() {
        val query = queryInput.text?.toString()?.trim().orEmpty()
        if (query.isBlank()) { statusView.setText(R.string.search_enter_query); return }
        val token = generation.incrementAndGet()
        adapter.submitList(emptyList())
        nextCursor = null
        runPage(token, "start_search_session_json", query, append = false)
    }

    private fun loadMore() {
        val cursor = nextCursor ?: return
        runPage(generation.get(), "continue_search_session_json", cursor, append = true)
    }

    private fun runPage(token: Int, method: String, argument: String, append: Boolean) {
        setBusy(true)
        statusView.setText(R.string.search_searching)
        searchExecutor.execute {
            val outcome = runCatching {
                if (!Python.isStarted()) error("Python runtime is not ready")
                JSONObject(Python.getInstance().getModule("video_downloader.media_search")
                    .callAttr(method, argument).toString())
            }
            runOnUiThread {
                if (token != generation.get() || isFinishing || isDestroyed) return@runOnUiThread
                setBusy(false)
                outcome.onSuccess { root ->
                    if (root.optString("error") == "restart_search") {
                        nextCursor = null
                        moreButton.visibility = View.GONE
                        statusView.setText(R.string.search_restart)
                        return@onSuccess
                    }
                    val parsed = buildList {
                        val array = root.optJSONArray("results") ?: return@buildList
                        for (i in 0 until array.length()) {
                            val item = array.optJSONObject(i) ?: continue
                            add(SearchResult(
                                id = item.optString("id", item.optString("url")),
                                title = item.optString("title", getString(R.string.player_unknown_title)),
                                url = item.optString("url"), thumbnail = item.optString("thumbnail"),
                                uploader = item.optString("uploader"),
                                durationSeconds = if (item.isNull("duration")) null else item.optInt("duration"),
                            ))
                        }
                    }
                    val combined = if (append) adapter.currentList + parsed else parsed
                    adapter.submitList(combined.distinctBy { it.id })
                    nextCursor = root.optString("next_cursor").takeIf { it.isNotBlank() && it != "null" }
                    moreButton.visibility = if (nextCursor == null) View.GONE else View.VISIBLE
                    statusView.text = if (combined.isEmpty()) getString(R.string.search_no_results)
                    else resources.getQuantityString(R.plurals.search_results_count, combined.size, combined.size)
                }.onFailure { statusView.text = getString(R.string.search_failed, it.message ?: "unknown error") }
            }
        }
    }

    private fun setBusy(busy: Boolean) { searchButton.isEnabled = !busy; moreButton.isEnabled = !busy }

    private fun enqueue(result: SearchResult, audioOnly: Boolean, button: Button) {
        if (result.url.isBlank()) return
        button.isEnabled = false
        statusView.setText(R.string.search_queueing)
        searchExecutor.execute {
            val queueResult = runCatching { LocalApiClient.enqueue(this, result.url, audioOnly) }
                .getOrElse { LocalApiClient.QueueResult(false, error = it.message) }
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                button.isEnabled = true
                if (queueResult.ok) {
                    statusView.text = getString(R.string.search_queued, result.title)
                    Toast.makeText(this, R.string.search_download_started, Toast.LENGTH_SHORT).show()
                } else statusView.text = queueResult.error ?: getString(R.string.search_queue_failed)
            }
        }
    }

    private fun loadThumbnail(result: SearchResult, image: ImageView) {
        image.tag = result.id
        image.setImageDrawable(null)
        thumbnailCache.get(result.thumbnail)?.let { image.setImageBitmap(it); return }
        val parsed = runCatching { URI(result.thumbnail).toURL() }.getOrNull() ?: return
        if (parsed.protocol != "https" || parsed.host !in THUMBNAIL_HOSTS) return
        thumbnailExecutor.execute {
            val bitmap = runCatching {
                val connection = parsed.openConnection().apply { connectTimeout = 4_000; readTimeout = 6_000 }
                connection.getInputStream().use { stream -> BitmapFactory.decodeStream(stream) }
            }.getOrNull() ?: return@execute
            thumbnailCache.put(result.thumbnail, bitmap)
            runOnUiThread { if (image.tag == result.id) image.setImageBitmap(bitmap) }
        }
    }

    override fun onDestroy() {
        generation.incrementAndGet(); searchExecutor.shutdownNow(); thumbnailExecutor.shutdownNow()
        super.onDestroy()
    }

    data class SearchResult(val id: String, val title: String, val url: String, val thumbnail: String,
                            val uploader: String, val durationSeconds: Int?)

    private class SearchAdapter(
        val enqueue: (SearchResult, Boolean, Button) -> Unit,
        val thumbnail: (SearchResult, ImageView) -> Unit,
    ) : ListAdapter<SearchResult, SearchAdapter.Holder>(DIFF) {
        class Holder(view: View) : RecyclerView.ViewHolder(view) {
            val image: ImageView = view.findViewById(R.id.search_result_thumbnail)
            val title: TextView = view.findViewById(R.id.search_result_title)
            val detail: TextView = view.findViewById(R.id.search_result_detail)
            val video: Button = view.findViewById(R.id.search_result_video)
            val audio: Button = view.findViewById(R.id.search_result_audio)
        }
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = Holder(
            LayoutInflater.from(parent.context).inflate(R.layout.item_search_result, parent, false))
        override fun onBindViewHolder(holder: Holder, position: Int) {
            val item = getItem(position)
            holder.title.text = item.title
            holder.detail.text = listOfNotNull(item.uploader.takeIf(String::isNotBlank), format(item.durationSeconds)).joinToString(" · ")
            holder.video.setOnClickListener { enqueue(item, false, holder.video) }
            holder.audio.setOnClickListener { enqueue(item, true, holder.audio) }
            thumbnail(item, holder.image)
        }
        override fun onViewRecycled(holder: Holder) { holder.image.tag = null; holder.image.setImageDrawable(null) }
        companion object {
            val DIFF = object : DiffUtil.ItemCallback<SearchResult>() {
                override fun areItemsTheSame(old: SearchResult, new: SearchResult) = old.id == new.id
                override fun areContentsTheSame(old: SearchResult, new: SearchResult) = old == new
            }
            fun format(seconds: Int?): String? {
                if (seconds == null || seconds <= 0) return null
                val h = seconds / 3600; val m = seconds % 3600 / 60; val s = seconds % 60
                return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
            }
        }
    }

    companion object { private val THUMBNAIL_HOSTS = setOf("i.ytimg.com", "img.youtube.com") }
}
