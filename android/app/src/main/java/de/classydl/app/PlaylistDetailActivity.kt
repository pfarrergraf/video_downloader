package de.classydl.app

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ContextThemeWrapper
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageButton
import android.widget.PopupMenu
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.media3.common.Player
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONArray
import org.json.JSONObject

/**
 * Browses one playlist's tracks and starts playback of the whole playlist
 * (normal or shuffled, with a repeat mode) or of one specific track — tapping
 * the row body plays from that track; opening this screen at all (rather
 * than immediately playing) is what MediaHistoryActivity's playlist card tap
 * does, distinct from its own quick-play button.
 */
class PlaylistDetailActivity : AppCompatActivity() {
    private lateinit var store: MediaLibraryStore
    private lateinit var thumbnailLoader: MediaThumbnailLoader
    private lateinit var adapter: LibraryAdapter
    private lateinit var normalHeader: View
    private lateinit var selectionHeader: View
    private lateinit var selectionCount: TextView
    private lateinit var titleView: TextView
    private lateinit var subtitleView: TextView
    private lateinit var emptyView: TextView
    private lateinit var repeatButton: Button

    private var playlistId: Long = -1L
    private var repeatMode = Player.REPEAT_MODE_OFF
    private var visibleTracks: List<MediaLibraryStore.Media> = emptyList()
    private val selectedMediaIds = mutableSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        playlistId = intent.getLongExtra(EXTRA_PLAYLIST_ID, -1L)
        if (playlistId < 0) { finish(); return }
        setContentView(R.layout.activity_playlist_detail)

        store = MediaLibraryStore(this)
        thumbnailLoader = MediaThumbnailLoader(this)
        adapter = LibraryAdapter(thumbnailLoader, Callbacks())

        normalHeader = findViewById(R.id.playlist_detail_normal_header)
        selectionHeader = findViewById(R.id.playlist_detail_selection_header)
        selectionCount = findViewById(R.id.playlist_detail_selection_count)
        titleView = findViewById(R.id.playlist_detail_title)
        subtitleView = findViewById(R.id.playlist_detail_subtitle)
        emptyView = findViewById(R.id.playlist_detail_empty)
        repeatButton = findViewById(R.id.playlist_detail_repeat)
        titleView.text = intent.getStringExtra(EXTRA_PLAYLIST_NAME).orEmpty()

        findViewById<ViewGroup>(R.id.playlist_detail_back).setOnClickListener { finish() }
        findViewById<Button>(R.id.playlist_detail_play).setOnClickListener { play(shuffle = false) }
        findViewById<Button>(R.id.playlist_detail_shuffle).setOnClickListener { play(shuffle = true) }
        repeatButton.setOnClickListener { cycleRepeatMode() }
        findViewById<ImageButton>(R.id.playlist_detail_selection_close).setOnClickListener { clearSelection() }
        findViewById<ImageButton>(R.id.playlist_detail_selection_play).setOnClickListener {
            playTracks(visibleTracks.filter { it.id in selectedMediaIds }, shuffle = false, repeatMode = repeatMode)
        }
        findViewById<ImageButton>(R.id.playlist_detail_selection_remove).setOnClickListener { removeSelectedFromPlaylist() }
        findViewById<ImageButton>(R.id.playlist_detail_selection_delete).setOnClickListener { confirmDeleteSelected() }
        updateRepeatButton()

        findViewById<RecyclerView>(R.id.playlist_detail_list).apply {
            layoutManager = LinearLayoutManager(this@PlaylistDetailActivity)
            adapter = this@PlaylistDetailActivity.adapter
        }
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onDestroy() {
        thumbnailLoader.shutdown()
        store.close()
        super.onDestroy()
    }

    private fun render() {
        val tracks = store.playlistMedia(playlistId)
        visibleTracks = tracks
        emptyView.visibility = if (tracks.isEmpty()) View.VISIBLE else View.GONE
        subtitleView.text = resources.getQuantityString(R.plurals.playlist_detail_track_count, tracks.size, tracks.size)
        adapter.submitList(tracks.map { LibraryRow.MediaRow(it) })
        updateSelectionHeader()
    }

    private fun isSelecting() = selectedMediaIds.isNotEmpty()

    private fun clearSelection() {
        selectedMediaIds.clear()
        updateSelectionHeader()
        adapter.notifyDataSetChanged()
    }

    private fun updateSelectionHeader() {
        val selecting = isSelecting()
        normalHeader.visibility = if (selecting) View.GONE else View.VISIBLE
        selectionHeader.visibility = if (selecting) View.VISIBLE else View.GONE
        if (selecting) selectionCount.text = getString(R.string.library_selection_count, selectedMediaIds.size)
    }

    private fun toggleSelection(media: MediaLibraryStore.Media) {
        if (!selectedMediaIds.remove(media.id)) selectedMediaIds.add(media.id)
        updateSelectionHeader()
        adapter.notifyDataSetChanged()
    }

    private fun removeSelectedFromPlaylist() {
        selectedMediaIds.toList().forEach { store.removeFromPlaylist(playlistId, it) }
        clearSelection()
        render()
    }

    private fun confirmDeleteSelected() {
        val items = visibleTracks.filter { it.id in selectedMediaIds }
        if (items.isEmpty()) return
        AlertDialog.Builder(this).setMessage(R.string.library_delete_file_confirm)
            .setNegativeButton(R.string.library_cancel, null)
            .setPositiveButton(R.string.library_delete_file) { _, _ ->
                val anyFailed = items.map { store.deleteFile(it) }.any { !it }
                if (anyFailed) toast(R.string.player_file_unavailable)
                clearSelection()
                render()
            }.show()
    }

    private fun cycleRepeatMode() {
        repeatMode = when (repeatMode) {
            Player.REPEAT_MODE_OFF -> Player.REPEAT_MODE_ALL
            Player.REPEAT_MODE_ALL -> Player.REPEAT_MODE_ONE
            else -> Player.REPEAT_MODE_OFF
        }
        updateRepeatButton()
    }

    private fun updateRepeatButton() {
        val descriptionRes = when (repeatMode) {
            Player.REPEAT_MODE_ALL -> R.string.playlist_repeat_all
            Player.REPEAT_MODE_ONE -> R.string.playlist_repeat_one
            else -> R.string.playlist_repeat_off
        }
        // Same emoji-not-vector choice as PlayerActivity's seek/volume
        // bubble: universally rendered, no new localized strings needed,
        // and 🔂 already bakes the "repeat one" concept into the glyph.
        repeatButton.text = if (repeatMode == Player.REPEAT_MODE_ONE) "🔂" else "🔁"
        repeatButton.alpha = if (repeatMode == Player.REPEAT_MODE_OFF) 0.5f else 1f
        repeatButton.contentDescription = getString(descriptionRes)
    }

    private fun play(shuffle: Boolean) = playTracks(visibleTracks, shuffle, repeatMode)

    private fun playFrom(media: MediaLibraryStore.Media) {
        val startIndex = visibleTracks.indexOfFirst { it.id == media.id }
        val ordered = if (startIndex <= 0) visibleTracks else visibleTracks.drop(startIndex) + visibleTracks.take(startIndex)
        playTracks(ordered, shuffle = false, repeatMode = repeatMode)
    }

    private fun playTracks(tracks: List<MediaLibraryStore.Media>, shuffle: Boolean, repeatMode: Int) {
        val readable = tracks.filter { canRead(it.uri) }
        if (readable.isEmpty()) { toast(R.string.library_playlist_empty); return }
        val array = JSONArray()
        readable.forEach { array.put(JSONObject().put("uri", it.uri).put("title", it.title).put("mimeType", it.mimeType ?: "")) }
        val first = readable.first()
        startActivity(
            Intent(this, PlayerActivity::class.java).setAction(PlayerActivity.ACTION_PLAY_INTERNAL)
                .setDataAndType(Uri.parse(first.uri), first.mimeType)
                .putExtra(PlayerActivity.EXTRA_PLAYLIST_JSON, array.toString())
                .putExtra(PlayerActivity.EXTRA_SHUFFLE, shuffle)
                .putExtra(PlayerActivity.EXTRA_REPEAT_MODE, repeatMode)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),
        )
    }

    private fun canRead(uri: String) = runCatching { contentResolver.openFileDescriptor(Uri.parse(uri), "r")?.use { true } ?: false }.getOrDefault(false)
    private fun toast(text: Int) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()

    private fun showTrackMenu(media: MediaLibraryStore.Media, anchor: View) {
        val popup = PopupMenu(ContextThemeWrapper(this, android.R.style.ThemeOverlay_Material_Dark), anchor)
        popup.inflate(R.menu.media_item_actions)
        popup.menu.findItem(R.id.action_remove_from_playlist).isVisible = true
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_add_to_playlist -> choosePlaylistForAdd(media)
                R.id.action_remove_from_playlist -> { store.removeFromPlaylist(playlistId, media.id); render() }
                R.id.action_remove -> { store.removeFromLibrary(media.id); render() }
                R.id.action_delete -> confirmDeleteFile(media)
            }
            true
        }
        popup.show()
    }

    private fun choosePlaylistForAdd(media: MediaLibraryStore.Media) {
        val playlists = store.playlists()
        AlertDialog.Builder(this).setTitle(R.string.library_add_to_playlist)
            .setItems(playlists.map { it.name }.toTypedArray()) { _, which -> store.addToPlaylist(playlists[which].id, media.id) }
            .setNegativeButton(R.string.library_cancel, null)
            .show()
    }

    private fun confirmDeleteFile(media: MediaLibraryStore.Media) {
        AlertDialog.Builder(this).setMessage(R.string.library_delete_file_confirm)
            .setNegativeButton(R.string.library_cancel, null)
            .setPositiveButton(R.string.library_delete_file) { _, _ ->
                if (!store.deleteFile(media)) toast(R.string.player_file_unavailable)
                render()
            }.show()
    }

    private inner class Callbacks : LibraryAdapter.Callbacks {
        override fun onMediaClick(media: MediaLibraryStore.Media) {
            if (isSelecting()) toggleSelection(media) else playFrom(media)
        }

        override fun onMediaLongClick(media: MediaLibraryStore.Media) = toggleSelection(media)
        override fun onMediaOverflow(media: MediaLibraryStore.Media, anchor: View) = showTrackMenu(media, anchor)
        override fun isMediaSelected(media: MediaLibraryStore.Media) = media.id in selectedMediaIds

        override fun onPlaylistClick(playlist: MediaLibraryStore.Playlist) {}
        override fun onPlaylistLongClick(playlist: MediaLibraryStore.Playlist) {}
        override fun onPlaylistPlay(playlist: MediaLibraryStore.Playlist) {}
        override fun onPlaylistOverflow(playlist: MediaLibraryStore.Playlist, anchor: View) {}
        override fun isPlaylistSelected(playlist: MediaLibraryStore.Playlist) = false
        override fun isSelectionMode() = isSelecting()
    }

    companion object {
        const val EXTRA_PLAYLIST_ID = "de.classydl.app.extra.PLAYLIST_ID"
        const val EXTRA_PLAYLIST_NAME = "de.classydl.app.extra.PLAYLIST_NAME"
    }
}
