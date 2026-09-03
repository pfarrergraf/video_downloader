package de.classydl.app

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ContextThemeWrapper
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
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
import java.util.concurrent.Executors

/**
 * Native local library: Ordner (all downloaded/played files, grouped by the
 * on-device download subfolder) and Playlists tabs, WhatsApp-style
 * long-press multi-select, and per-row overflow menus instead of always-
 * visible text action buttons. Kept under the historic activity name for
 * intent compatibility.
 */
class MediaHistoryActivity : AppCompatActivity() {
    private lateinit var store: MediaLibraryStore
    private lateinit var thumbnailLoader: MediaThumbnailLoader
    private lateinit var adapter: LibraryAdapter
    private lateinit var normalHeader: View
    private lateinit var selectionHeader: View
    private lateinit var selectionCount: TextView
    private lateinit var selectionPlay: View
    private lateinit var selectionMove: View
    private lateinit var tabFolders: Button
    private lateinit var tabPlaylists: Button
    private lateinit var newPlaylistButton: Button
    private lateinit var clearHistoryButton: Button
    private lateinit var emptyView: TextView
    private val io = Executors.newSingleThreadExecutor()

    private enum class Tab { FOLDERS, PLAYLISTS }

    private var currentTab = Tab.FOLDERS
    private var visibleMedia: List<MediaLibraryStore.Media> = emptyList()
    private var visiblePlaylists: List<MediaLibraryStore.Playlist> = emptyList()
    private val selectedMediaIds = mutableSetOf<String>()
    private val selectedPlaylistIds = mutableSetOf<Long>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_media_history)
        store = MediaLibraryStore(this)
        thumbnailLoader = MediaThumbnailLoader(this)
        adapter = LibraryAdapter(thumbnailLoader, LibraryRowCallbacks())

        normalHeader = findViewById(R.id.normal_header)
        selectionHeader = findViewById(R.id.selection_header)
        selectionCount = findViewById(R.id.selection_count)
        selectionPlay = findViewById(R.id.selection_play)
        selectionMove = findViewById(R.id.selection_move)
        tabFolders = findViewById(R.id.tab_folders)
        tabPlaylists = findViewById(R.id.tab_playlists)
        newPlaylistButton = findViewById(R.id.library_new_playlist)
        clearHistoryButton = findViewById(R.id.history_clear)
        emptyView = findViewById(R.id.history_empty)

        findViewById<ViewGroup>(R.id.history_back).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.history_search).apply {
            visibility = if (BuildConfig.PLAY_POLICY_RESTRICTED) View.GONE else View.VISIBLE
            setOnClickListener { startActivity(Intent(this@MediaHistoryActivity, SearchActivity::class.java)) }
        }
        findViewById<ImageButton>(R.id.history_play_all).setOnClickListener {
            val recent = store.media(100)
            if (recent.isEmpty()) toast(R.string.library_playlist_empty) else playMediaList(recent)
        }
        findViewById<ImageButton>(R.id.selection_close).setOnClickListener { clearSelection() }
        selectionPlay.setOnClickListener {
            playMediaList(visibleMedia.filter { it.id in selectedMediaIds })
        }
        selectionMove.setOnClickListener { promptMoveSelection() }
        findViewById<ImageButton>(R.id.selection_delete).setOnClickListener { confirmDeleteSelection() }
        tabFolders.setOnClickListener { selectTab(Tab.FOLDERS) }
        tabPlaylists.setOnClickListener { selectTab(Tab.PLAYLISTS) }
        newPlaylistButton.setOnClickListener { promptPlaylistName() }
        clearHistoryButton.setOnClickListener { store.clearPlaybackHistory(); render() }

        findViewById<RecyclerView>(R.id.library_list).apply {
            layoutManager = LinearLayoutManager(this@MediaHistoryActivity)
            adapter = this@MediaHistoryActivity.adapter
        }
        updateTabStyles()
    }

    override fun onResume() {
        super.onResume()
        io.execute {
            store.reconcileDownloads(); store.pruneUnreadable()
            runOnUiThread { if (!isFinishing && !isDestroyed) render() }
        }
    }

    override fun onDestroy() {
        io.shutdownNow()
        thumbnailLoader.shutdown()
        store.close()
        super.onDestroy()
    }

    private fun selectTab(tab: Tab) {
        if (currentTab == tab) return
        currentTab = tab
        clearSelection()
        updateTabStyles()
        render()
    }

    private fun updateTabStyles() {
        val foldersActive = currentTab == Tab.FOLDERS
        tabFolders.setBackgroundResource(if (foldersActive) R.drawable.bg_button_primary else R.drawable.bg_button_secondary)
        tabPlaylists.setBackgroundResource(if (foldersActive) R.drawable.bg_button_secondary else R.drawable.bg_button_primary)
        tabFolders.setTextColor(if (foldersActive) 0xFFFFFFFF.toInt() else 0xFFF3F1FB.toInt())
        tabPlaylists.setTextColor(if (foldersActive) 0xFFF3F1FB.toInt() else 0xFFFFFFFF.toInt())
        newPlaylistButton.visibility = if (foldersActive) View.GONE else View.VISIBLE
        clearHistoryButton.visibility = if (foldersActive) View.VISIBLE else View.GONE
    }

    private fun render() {
        when (currentTab) {
            Tab.FOLDERS -> renderFolders()
            Tab.PLAYLISTS -> renderPlaylists()
        }
        updateSelectionHeader()
    }

    private fun renderFolders() {
        val media = store.media(300)
        visibleMedia = media
        emptyView.visibility = if (media.isEmpty()) View.VISIBLE else View.GONE
        emptyView.setText(R.string.history_empty)
        val rows = buildList {
            media.groupBy { folderLabel(it.relativePath) }.forEach { (folder, items) ->
                add(LibraryRow.Header(folder))
                items.forEach { add(LibraryRow.MediaRow(it)) }
            }
        }
        adapter.submitList(rows)
    }

    private fun renderPlaylists() {
        val playlists = store.playlists()
        visiblePlaylists = playlists
        emptyView.visibility = if (playlists.isEmpty()) View.VISIBLE else View.GONE
        emptyView.setText(R.string.library_no_playlists)
        val rows = playlists.map { playlist ->
            val items = store.playlistMedia(playlist.id)
            LibraryRow.PlaylistRow(playlist, items.size, items.firstOrNull())
        }
        adapter.submitList(rows)
    }

    private fun folderLabel(relativePath: String?): String {
        val parent = relativePath?.substringBeforeLast('/', "")
        return parent?.takeIf { it.isNotBlank() } ?: getString(R.string.library_folder_unsorted)
    }

    private fun isSelecting() = selectedMediaIds.isNotEmpty() || selectedPlaylistIds.isNotEmpty()

    private fun clearSelection() {
        selectedMediaIds.clear()
        selectedPlaylistIds.clear()
        updateSelectionHeader()
        adapter.notifyDataSetChanged()
    }

    private fun updateSelectionHeader() {
        val selecting = isSelecting()
        normalHeader.visibility = if (selecting) View.GONE else View.VISIBLE
        selectionHeader.visibility = if (selecting) View.VISIBLE else View.GONE
        if (!selecting) return
        selectionCount.text = getString(R.string.library_selection_count, selectedMediaIds.size + selectedPlaylistIds.size)
        val trackMode = selectedMediaIds.isNotEmpty()
        selectionPlay.visibility = if (trackMode) View.VISIBLE else View.GONE
        selectionMove.visibility = if (trackMode) View.VISIBLE else View.GONE
    }

    private fun toggleMediaSelection(media: MediaLibraryStore.Media) {
        if (!selectedMediaIds.remove(media.id)) selectedMediaIds.add(media.id)
        updateSelectionHeader()
        adapter.notifyDataSetChanged()
    }

    private fun togglePlaylistSelection(playlist: MediaLibraryStore.Playlist) {
        if (!selectedPlaylistIds.remove(playlist.id)) selectedPlaylistIds.add(playlist.id)
        updateSelectionHeader()
        adapter.notifyDataSetChanged()
    }

    private inner class LibraryRowCallbacks : LibraryAdapter.Callbacks {
        override fun onMediaClick(media: MediaLibraryStore.Media) {
            if (isSelecting()) toggleMediaSelection(media) else playMediaList(listOf(media))
        }

        override fun onMediaLongClick(media: MediaLibraryStore.Media) = toggleMediaSelection(media)
        override fun onMediaOverflow(media: MediaLibraryStore.Media, anchor: View) = showMediaMenu(media, anchor)
        override fun isMediaSelected(media: MediaLibraryStore.Media) = media.id in selectedMediaIds

        override fun onPlaylistClick(playlist: MediaLibraryStore.Playlist) {
            if (isSelecting()) togglePlaylistSelection(playlist) else openPlaylistDetail(playlist)
        }

        override fun onPlaylistLongClick(playlist: MediaLibraryStore.Playlist) = togglePlaylistSelection(playlist)

        override fun onPlaylistPlay(playlist: MediaLibraryStore.Playlist) {
            val items = store.playlistMedia(playlist.id)
            if (items.isEmpty()) toast(R.string.library_playlist_empty) else playMediaList(items)
        }

        override fun onPlaylistOverflow(playlist: MediaLibraryStore.Playlist, anchor: View) = showPlaylistMenu(playlist, anchor)
        override fun isPlaylistSelected(playlist: MediaLibraryStore.Playlist) = playlist.id in selectedPlaylistIds
        override fun isSelectionMode() = isSelecting()
    }

    private fun openPlaylistDetail(playlist: MediaLibraryStore.Playlist) {
        startActivity(
            Intent(this, PlaylistDetailActivity::class.java)
                .putExtra(PlaylistDetailActivity.EXTRA_PLAYLIST_ID, playlist.id)
                .putExtra(PlaylistDetailActivity.EXTRA_PLAYLIST_NAME, playlist.name),
        )
    }

    private fun showMediaMenu(media: MediaLibraryStore.Media, anchor: View) {
        val popup = PopupMenu(darkPopupContext(), anchor)
        popup.inflate(R.menu.media_item_actions)
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_add_to_playlist -> choosePlaylistForAdd(listOf(media.id))
                R.id.action_remove -> { store.removeFromLibrary(media.id); render() }
                R.id.action_delete -> confirmDeleteFiles(listOf(media))
            }
            true
        }
        popup.show()
    }

    private fun showPlaylistMenu(playlist: MediaLibraryStore.Playlist, anchor: View) {
        val popup = PopupMenu(darkPopupContext(), anchor)
        popup.inflate(R.menu.playlist_actions)
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_rename_playlist -> promptPlaylistName(playlist)
                R.id.action_delete_playlist -> confirmDeletePlaylists(listOf(playlist))
            }
            true
        }
        popup.show()
    }

    private fun darkPopupContext() = ContextThemeWrapper(this, android.R.style.ThemeOverlay_Material_Dark)

    private fun choosePlaylistForAdd(mediaIds: List<String>) {
        val playlists = store.playlists()
        if (playlists.isEmpty()) {
            promptPlaylistName(onCreated = { id -> mediaIds.forEach { store.addToPlaylist(id, it) }; clearSelection(); render() })
            return
        }
        AlertDialog.Builder(this).setTitle(R.string.library_add_to_playlist)
            .setItems(playlists.map { it.name }.toTypedArray()) { _, which ->
                mediaIds.forEach { store.addToPlaylist(playlists[which].id, it) }
                clearSelection()
                render()
            }
            .setNegativeButton(R.string.library_cancel, null)
            .show()
    }

    private fun promptMoveSelection() {
        if (selectedMediaIds.isEmpty()) return
        choosePlaylistForAdd(selectedMediaIds.toList())
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

    private fun confirmDeleteFiles(items: List<MediaLibraryStore.Media>) {
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

    private fun confirmDeletePlaylists(playlists: List<MediaLibraryStore.Playlist>) {
        if (playlists.isEmpty()) return
        AlertDialog.Builder(this).setMessage(R.string.library_delete_confirm_generic)
            .setNegativeButton(R.string.library_cancel, null)
            .setPositiveButton(R.string.library_delete_playlist) { _, _ ->
                playlists.forEach { store.deletePlaylist(it.id) }
                clearSelection()
                render()
            }.show()
    }

    private fun confirmDeleteSelection() {
        if (selectedMediaIds.isNotEmpty()) {
            confirmDeleteFiles(visibleMedia.filter { it.id in selectedMediaIds })
        } else if (selectedPlaylistIds.isNotEmpty()) {
            confirmDeletePlaylists(visiblePlaylists.filter { it.id in selectedPlaylistIds })
        }
    }

    private fun playMediaList(items: List<MediaLibraryStore.Media>, shuffle: Boolean = false, repeatMode: Int = Player.REPEAT_MODE_OFF) {
        val readable = items.filter { canRead(it.uri) }
        if (readable.isEmpty()) return
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
}
