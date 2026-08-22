package de.classydl.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject

/** Local-only "Continue" and recently played library. */
class MediaHistoryActivity : AppCompatActivity() {
    private lateinit var store: PlaybackRetentionStore
    private lateinit var container: LinearLayout
    private lateinit var emptyView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_history)
        store = PlaybackRetentionStore(this)
        container = findViewById(R.id.history_results)
        emptyView = findViewById(R.id.history_empty)

        findViewById<ViewGroup>(R.id.history_back).setOnClickListener { finish() }
        findViewById<Button>(R.id.history_search).setOnClickListener {
            startActivity(Intent(this, SearchActivity::class.java))
        }
        findViewById<Button>(R.id.history_play_all).setOnClickListener { playAllRecent() }
        findViewById<Button>(R.id.history_clear).setOnClickListener {
            store.clearHistory()
            render()
        }
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    private fun render() {
        container.removeAllViews()
        val items = store.recent(30)
        emptyView.visibility = if (items.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
        findViewById<Button>(R.id.history_play_all).isEnabled = items.isNotEmpty()
        items.forEach { entry ->
            val button = Button(this).apply {
                isAllCaps = false
                gravity = Gravity.START or Gravity.CENTER_VERTICAL
                text = buildString {
                    append(entry.title)
                    append('\n')
                    append(
                        if (entry.isMeaningfulResume) {
                            getString(R.string.history_continue_at, formatTime(entry.positionMs))
                        } else {
                            getString(R.string.history_play_again)
                        },
                    )
                    if (entry.durationMs > 0L) {
                        append(" · ")
                        append(formatTime(entry.durationMs))
                    }
                }
                setOnClickListener { play(entry) }
            }
            container.addView(
                button,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                ).apply { bottomMargin = dp(10) },
            )
        }
    }

    private fun play(entry: PlaybackRetentionStore.Entry) {
        if (!canRead(entry)) {
            store.remove(entry.uri)
            render()
            Toast.makeText(this, R.string.player_file_unavailable, Toast.LENGTH_SHORT).show()
            return
        }
        val intent = Intent(this, PlayerActivity::class.java)
            .setAction(PlayerActivity.ACTION_PLAY_INTERNAL)
            .setDataAndType(Uri.parse(entry.uri), entry.mimeType)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(intent)
    }

    private fun playAllRecent() {
        val recent = store.recent(20)
        val unavailable = recent.filterNot(::canRead)
        unavailable.forEach { store.remove(it.uri) }
        val items = recent - unavailable.toSet()
        if (unavailable.isNotEmpty()) render()
        if (items.isEmpty()) return
        val array = JSONArray()
        items.forEach { entry ->
            array.put(
                JSONObject()
                    .put("uri", entry.uri)
                    .put("title", entry.title)
                    .put("mimeType", entry.mimeType ?: ""),
            )
        }
        val first = items.first()
        startActivity(
            Intent(this, PlayerActivity::class.java)
                .setAction(PlayerActivity.ACTION_PLAY_INTERNAL)
                .setDataAndType(Uri.parse(first.uri), first.mimeType)
                .putExtra(PlayerActivity.EXTRA_PLAYLIST_JSON, array.toString())
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),
        )
    }

    private fun canRead(entry: PlaybackRetentionStore.Entry): Boolean = runCatching {
        contentResolver.openFileDescriptor(Uri.parse(entry.uri), "r")?.use { true } ?: false
    }.getOrDefault(false)

    private fun formatTime(ms: Long): String {
        val totalSeconds = (ms / 1000L).coerceAtLeast(0L)
        val hours = totalSeconds / 3600L
        val minutes = (totalSeconds % 3600L) / 60L
        val seconds = totalSeconds % 60L
        return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, seconds)
        else "%d:%02d".format(minutes, seconds)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
