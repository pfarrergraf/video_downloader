package de.classydl.app

import java.io.File

/** Stable media MIME types shared by notification intents on OEM Android builds. */
object MediaMimeTypes {
    private val byExtension = mapOf(
        "mp4" to "video/mp4",
        "m4v" to "video/x-m4v",
        "webm" to "video/webm",
        "mkv" to "video/x-matroska",
        "mov" to "video/quicktime",
        "mp3" to "audio/mpeg",
        "m4a" to "audio/mp4",
        "aac" to "audio/aac",
        "opus" to "audio/ogg",
        "ogg" to "audio/ogg",
        "wav" to "audio/wav",
        "flac" to "audio/flac",
    )

    fun forFile(file: File): String = byExtension[file.extension.lowercase()]
        ?: "application/octet-stream"
}
