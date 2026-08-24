package de.classydl.app

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors

/** Native local library. Kept under the historic activity name for intent compatibility. */
class MediaHistoryActivity : AppCompatActivity() {
    private lateinit var store: MediaLibraryStore
    private lateinit var container: LinearLayout
    private lateinit var playlistsContainer: LinearLayout
    private lateinit var emptyView: TextView
    private val io = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_history)
        store = MediaLibraryStore(this)
        container = findViewById(R.id.history_results)
        playlistsContainer = findViewById(R.id.library_playlists)
        emptyView = findViewById(R.id.history_empty)
        findViewById<ViewGroup>(R.id.history_back).setOnClickListener { finish() }
        findViewById<Button>(R.id.history_search).setOnClickListener { startActivity(Intent(this, SearchActivity::class.java)) }
        findViewById<Button>(R.id.history_play_all).setOnClickListener { playItems(store.media(100)) }
        findViewById<Button>(R.id.history_clear).setOnClickListener { store.clearPlaybackHistory(); render() }
        findViewById<Button>(R.id.library_new_playlist).setOnClickListener { promptPlaylistName() }
    }

    override fun onResume() {
        super.onResume()
        io.execute {
            store.reconcileDownloads(); store.pruneUnreadable()
            runOnUiThread { if (!isFinishing && !isDestroyed) render() }
        }
    }

    override fun onDestroy() { io.shutdownNow(); store.close(); super.onDestroy() }

    private fun render() {
        renderPlaylists()
        container.removeAllViews()
        val items = store.media(100)
        emptyView.visibility = if (items.isEmpty()) View.VISIBLE else View.GONE
        findViewById<Button>(R.id.history_play_all).isEnabled = items.isNotEmpty()
        items.forEach { media -> container.addView(mediaCard(media), marginParams()) }
    }

    private fun mediaCard(media: MediaLibraryStore.Media): View = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        addView(Button(this@MediaHistoryActivity).apply {
            isAllCaps = false; gravity = Gravity.START or Gravity.CENTER_VERTICAL
            text = buildString {
                append(media.title)
                media.lastPlayedAtMs?.let {
                    append('\n'); append(if (media.isMeaningfulResume) getString(R.string.history_continue_at, formatTime(media.positionMs))
                    else getString(R.string.history_play_again))
                }
            }
            setOnClickListener { playItems(listOf(media)) }
        })
        addView(LinearLayout(this@MediaHistoryActivity).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(action(R.string.library_add_to_playlist) { choosePlaylist(media) }, weighted())
            addView(action(R.string.library_remove) { store.removeFromLibrary(media.id); render() }, weighted())
            addView(action(R.string.library_delete_file) { confirmDelete(media) }, weighted())
        })
    }

    private fun renderPlaylists() {
        playlistsContainer.removeAllViews()
        store.playlists().forEach { playlist ->
            val items = store.playlistMedia(playlist.id)
            playlistsContainer.addView(LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                addView(TextView(this@MediaHistoryActivity).apply {
                    text = "${playlist.name} (${items.size})"; textSize = 18f; setTextColor(0xFFF3F1FB.toInt())
                })
                addView(LinearLayout(this@MediaHistoryActivity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    addView(action(R.string.history_play_all) { if (items.isEmpty()) toast(R.string.library_playlist_empty) else playItems(items) }, weighted())
                    addView(action(R.string.library_rename) { promptPlaylistName(playlist) }, weighted())
                    addView(action(R.string.library_delete_playlist) { store.deletePlaylist(playlist.id); render() }, weighted())
                })
                items.forEach { item -> addView(LinearLayout(this@MediaHistoryActivity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    addView(TextView(this@MediaHistoryActivity).apply { text = item.title; setTextColor(0xFFA5A0C0.toInt()) }, weighted())
                    addView(action(R.string.library_move_up) { store.movePlaylistItem(playlist.id, item.id, -1); render() })
                    addView(action(R.string.library_move_down) { store.movePlaylistItem(playlist.id, item.id, 1); render() })
                    addView(action(R.string.library_remove_from_playlist) { store.removeFromPlaylist(playlist.id, item.id); render() })
                }) }
            }, marginParams())
        }
    }

    private fun promptPlaylistName(existing: MediaLibraryStore.Playlist? = null, onCreated: ((Long) -> Unit)? = null) {
        val input = EditText(this).apply { hint = getString(R.string.library_playlist_name); setText(existing?.name.orEmpty()) }
        AlertDialog.Builder(this).setTitle(if (existing == null) R.string.library_new_playlist else R.string.library_rename)
            .setView(input).setNegativeButton(R.string.library_cancel, null)
            .setPositiveButton(if (existing == null) R.string.library_create else R.string.library_rename) { _, _ ->
                runCatching {
                    if (existing == null) store.createPlaylist(input.text.toString()).also { onCreated?.invoke(it) }
                    else store.renamePlaylist(existing.id, input.text.toString())
                }
                render()
            }.show()
    }

    private fun choosePlaylist(media: MediaLibraryStore.Media) {
        val playlists = store.playlists()
        if (playlists.isEmpty()) { promptPlaylistName(onCreated = { store.addToPlaylist(it, media.id) }); return }
        AlertDialog.Builder(this).setTitle(R.string.library_add_to_playlist)
            .setItems(playlists.map { it.name }.toTypedArray()) { _, which -> store.addToPlaylist(playlists[which].id, media.id); render() }
            .setNegativeButton(R.string.library_cancel, null).show()
    }

    private fun confirmDelete(media: MediaLibraryStore.Media) {
        AlertDialog.Builder(this).setMessage(R.string.library_delete_file_confirm)
            .setNegativeButton(R.string.library_cancel, null)
            .setPositiveButton(R.string.library_delete_file) { _, _ ->
                if (!store.deleteFile(media)) Toast.makeText(this, R.string.player_file_unavailable, Toast.LENGTH_SHORT).show()
                render()
            }.show()
    }

    private fun playItems(raw: List<MediaLibraryStore.Media>) {
        val items = raw.filter { canRead(it.uri) }
        if (items.isEmpty()) return
        val array = JSONArray()
        items.forEach { array.put(JSONObject().put("uri", it.uri).put("title", it.title).put("mimeType", it.mimeType ?: "")) }
        val first = items.first()
        startActivity(Intent(this, PlayerActivity::class.java).setAction(PlayerActivity.ACTION_PLAY_INTERNAL)
            .setDataAndType(Uri.parse(first.uri), first.mimeType)
            .putExtra(PlayerActivity.EXTRA_PLAYLIST_JSON, array.toString()).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION))
    }

    private fun canRead(uri: String) = runCatching { contentResolver.openFileDescriptor(Uri.parse(uri), "r")?.use { true } ?: false }.getOrDefault(false)
    private fun action(text: Int, params: LinearLayout.LayoutParams? = null, click: () -> Unit) = Button(this).apply {
        setText(text); isAllCaps = false; setOnClickListener { click() }; params?.let { layoutParams = it }
    }
    private fun weighted() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
    private fun marginParams() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { bottomMargin = dp(12) }
    private fun toast(text: Int) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
    private fun formatTime(ms: Long): String { val s = (ms / 1000).coerceAtLeast(0); return if (s >= 3600) "%d:%02d:%02d".format(s/3600,s%3600/60,s%60) else "%d:%02d".format(s/60,s%60) }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
