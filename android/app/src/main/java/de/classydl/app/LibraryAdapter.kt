package de.classydl.app

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView

/** One row in MediaHistoryActivity's library list: a folder-group header, a
 * track (Ordner tab), or a playlist card (Playlists tab). */
sealed class LibraryRow {
    data class Header(val label: String) : LibraryRow()
    data class MediaRow(val media: MediaLibraryStore.Media) : LibraryRow()
    data class PlaylistRow(
        val playlist: MediaLibraryStore.Playlist,
        val trackCount: Int,
        val cover: MediaLibraryStore.Media?,
    ) : LibraryRow()
}

/**
 * Single adapter for both tabs. Selection state (checkboxes) lives in the
 * host Activity, not in the submitted list, so any selection change calls
 * [RecyclerView.Adapter.notifyDataSetChanged] rather than going through
 * DiffUtil — the dataset itself (~a few hundred rows at most) is small
 * enough that this is simpler and cheap.
 */
class LibraryAdapter(
    private val thumbnails: MediaThumbnailLoader,
    private val callbacks: Callbacks,
) : ListAdapter<LibraryRow, RecyclerView.ViewHolder>(DIFF) {

    interface Callbacks {
        fun onMediaClick(media: MediaLibraryStore.Media)
        fun onMediaLongClick(media: MediaLibraryStore.Media)
        fun onMediaOverflow(media: MediaLibraryStore.Media, anchor: View)
        fun isMediaSelected(media: MediaLibraryStore.Media): Boolean

        fun onPlaylistClick(playlist: MediaLibraryStore.Playlist)
        fun onPlaylistLongClick(playlist: MediaLibraryStore.Playlist)
        fun onPlaylistPlay(playlist: MediaLibraryStore.Playlist)
        fun onPlaylistOverflow(playlist: MediaLibraryStore.Playlist, anchor: View)
        fun isPlaylistSelected(playlist: MediaLibraryStore.Playlist): Boolean

        fun isSelectionMode(): Boolean
    }

    class HeaderHolder(view: View) : RecyclerView.ViewHolder(view) {
        val label: TextView = view as TextView
    }

    class MediaHolder(view: View) : RecyclerView.ViewHolder(view) {
        val checkbox: CheckBox = view.findViewById(R.id.row_checkbox)
        val thumbnail: ImageView = view.findViewById(R.id.row_thumbnail)
        val title: TextView = view.findViewById(R.id.row_title)
        val subtitle: TextView = view.findViewById(R.id.row_subtitle)
        val overflow: ImageButton = view.findViewById(R.id.row_overflow)
    }

    class PlaylistHolder(view: View) : RecyclerView.ViewHolder(view) {
        val checkbox: CheckBox = view.findViewById(R.id.row_checkbox)
        val thumbnail: ImageView = view.findViewById(R.id.row_thumbnail)
        val title: TextView = view.findViewById(R.id.row_title)
        val subtitle: TextView = view.findViewById(R.id.row_subtitle)
        val play: ImageButton = view.findViewById(R.id.row_play)
        val overflow: ImageButton = view.findViewById(R.id.row_overflow)
    }

    override fun getItemViewType(position: Int) = when (getItem(position)) {
        is LibraryRow.Header -> TYPE_HEADER
        is LibraryRow.MediaRow -> TYPE_MEDIA
        is LibraryRow.PlaylistRow -> TYPE_PLAYLIST
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inflater = LayoutInflater.from(parent.context)
        return when (viewType) {
            TYPE_HEADER -> HeaderHolder(inflater.inflate(R.layout.item_section_header, parent, false))
            TYPE_MEDIA -> MediaHolder(inflater.inflate(R.layout.item_media_row, parent, false))
            else -> PlaylistHolder(inflater.inflate(R.layout.item_playlist_row, parent, false))
        }
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        when (val row = getItem(position)) {
            is LibraryRow.Header -> (holder as HeaderHolder).label.text = row.label
            is LibraryRow.MediaRow -> bindMedia(holder as MediaHolder, row.media)
            is LibraryRow.PlaylistRow -> bindPlaylist(holder as PlaylistHolder, row)
        }
    }

    override fun onViewRecycled(holder: RecyclerView.ViewHolder) {
        when (holder) {
            is MediaHolder -> thumbnails.cancel(holder.thumbnail)
            is PlaylistHolder -> thumbnails.cancel(holder.thumbnail)
            else -> {}
        }
    }

    private fun bindMedia(holder: MediaHolder, media: MediaLibraryStore.Media) {
        holder.title.text = media.title
        holder.subtitle.text = when {
            media.lastPlayedAtMs != null && media.isMeaningfulResume ->
                holder.itemView.context.getString(R.string.history_continue_at, formatTime(media.positionMs))
            media.lastPlayedAtMs != null -> holder.itemView.context.getString(R.string.history_play_again)
            else -> formatTime(media.durationMs).takeIf { media.durationMs > 0 }.orEmpty()
        }
        val placeholder = if (media.mimeType?.startsWith("video/") == true) {
            R.drawable.ic_generic_video
        } else {
            R.drawable.ic_generic_audio
        }
        thumbnails.load(media, holder.thumbnail, placeholder)
        val selecting = callbacks.isSelectionMode()
        holder.checkbox.visibility = if (selecting) View.VISIBLE else View.GONE
        // Non-interactive: the whole row is the tap target (see onMediaClick
        // below), so the checkbox only ever reflects state, never sets it —
        // otherwise its own default touch handling would toggle it without
        // updating the Activity's selectedMediaIds set.
        holder.checkbox.isClickable = false
        holder.checkbox.isChecked = callbacks.isMediaSelected(media)
        holder.overflow.visibility = if (selecting) View.GONE else View.VISIBLE
        holder.overflow.setOnClickListener { callbacks.onMediaOverflow(media, holder.overflow) }
        holder.itemView.setOnClickListener { callbacks.onMediaClick(media) }
        holder.itemView.setOnLongClickListener { callbacks.onMediaLongClick(media); true }
    }

    private fun bindPlaylist(holder: PlaylistHolder, row: LibraryRow.PlaylistRow) {
        holder.title.text = row.playlist.name
        holder.subtitle.text = holder.itemView.resources.getQuantityString(
            R.plurals.playlist_detail_track_count, row.trackCount, row.trackCount,
        )
        val cover = row.cover
        if (cover != null) {
            val placeholder = if (cover.mimeType?.startsWith("video/") == true) {
                R.drawable.ic_generic_video
            } else {
                R.drawable.ic_generic_audio
            }
            thumbnails.load(cover, holder.thumbnail, placeholder)
        } else {
            holder.thumbnail.setImageDrawable(null)
        }
        val selecting = callbacks.isSelectionMode()
        holder.checkbox.visibility = if (selecting) View.VISIBLE else View.GONE
        holder.checkbox.isClickable = false
        holder.checkbox.isChecked = callbacks.isPlaylistSelected(row.playlist)
        holder.play.visibility = if (selecting) View.GONE else View.VISIBLE
        holder.overflow.visibility = if (selecting) View.GONE else View.VISIBLE
        holder.play.setOnClickListener { callbacks.onPlaylistPlay(row.playlist) }
        holder.overflow.setOnClickListener { callbacks.onPlaylistOverflow(row.playlist, holder.overflow) }
        holder.itemView.setOnClickListener { callbacks.onPlaylistClick(row.playlist) }
        holder.itemView.setOnLongClickListener { callbacks.onPlaylistLongClick(row.playlist); true }
    }

    private fun formatTime(ms: Long): String {
        val s = (ms / 1000).coerceAtLeast(0)
        return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s % 3600 / 60, s % 60) else "%d:%02d".format(s / 60, s % 60)
    }

    companion object {
        private const val TYPE_HEADER = 0
        private const val TYPE_MEDIA = 1
        private const val TYPE_PLAYLIST = 2

        private val DIFF = object : DiffUtil.ItemCallback<LibraryRow>() {
            override fun areItemsTheSame(old: LibraryRow, new: LibraryRow): Boolean = when {
                old is LibraryRow.Header && new is LibraryRow.Header -> old.label == new.label
                old is LibraryRow.MediaRow && new is LibraryRow.MediaRow -> old.media.id == new.media.id
                old is LibraryRow.PlaylistRow && new is LibraryRow.PlaylistRow -> old.playlist.id == new.playlist.id
                else -> false
            }

            override fun areContentsTheSame(old: LibraryRow, new: LibraryRow): Boolean = old == new
        }
    }
}
