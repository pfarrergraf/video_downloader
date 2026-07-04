import AVFoundation
import CoreMedia
import Foundation

/// Muxes a separately-downloaded video-only and audio-only file into one playable
/// file, natively, with no ffmpeg (ffmpeg-kit is dead upstream, and iOS doesn't allow
/// apps to subprocess-exec bundled binaries anyway - see ios/README.md's "Download
/// engine" section). AVAssetExportSession's .passthrough preset can only remux
/// H.264/HEVC video + AAC audio without re-encoding; anything else (VP9/AV1 video,
/// Opus audio - common in higher-quality YouTube DASH tiers) isn't supported here, so
/// callers should fall back to leaving the two files separate when this throws.
enum MediaMerger {
    enum MergeError: Error {
        case incompatibleCodecs
        case exportFailed
    }

    static func merge(videoURL: URL, audioURL: URL) async throws -> URL {
        let videoAsset = AVURLAsset(url: videoURL)
        let audioAsset = AVURLAsset(url: audioURL)

        guard let videoTrack = try await videoAsset.loadTracks(withMediaType: .video).first,
              let audioTrack = try await audioAsset.loadTracks(withMediaType: .audio).first else {
            throw MergeError.incompatibleCodecs
        }
        guard try await isPassthroughCompatible(videoTrack: videoTrack, audioTrack: audioTrack) else {
            throw MergeError.incompatibleCodecs
        }

        let composition = AVMutableComposition()
        guard let compositionVideoTrack = composition.addMutableTrack(
                withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid),
              let compositionAudioTrack = composition.addMutableTrack(
                withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
            throw MergeError.exportFailed
        }

        let videoDuration = try await videoAsset.load(.duration)
        let audioDuration = try await audioAsset.load(.duration)
        let range = CMTimeRange(start: .zero, duration: CMTimeMinimum(videoDuration, audioDuration))

        try compositionVideoTrack.insertTimeRange(range, of: videoTrack, at: .zero)
        try compositionAudioTrack.insertTimeRange(range, of: audioTrack, at: .zero)

        let outputURL = videoURL
            .deletingLastPathComponent()
            .appendingPathComponent(videoURL.deletingPathExtension().lastPathComponent + "-merged")
            .appendingPathExtension("mp4")
        if FileManager.default.fileExists(atPath: outputURL.path) {
            try FileManager.default.removeItem(at: outputURL)
        }

        guard let exportSession = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetPassthrough) else {
            throw MergeError.exportFailed
        }
        exportSession.outputURL = outputURL
        exportSession.outputFileType = .mp4

        await exportSession.export()

        guard exportSession.status == .completed else {
            throw MergeError.exportFailed
        }
        return outputURL
    }

    private static func isPassthroughCompatible(videoTrack: AVAssetTrack, audioTrack: AVAssetTrack) async throws -> Bool {
        let videoDescriptions = try await videoTrack.load(.formatDescriptions)
        let audioDescriptions = try await audioTrack.load(.formatDescriptions)

        let compatibleVideoCodecs: Set<CMVideoCodecType> = [kCMVideoCodecType_H264, kCMVideoCodecType_HEVC]
        let videoOK = videoDescriptions.contains { compatibleVideoCodecs.contains(CMFormatDescriptionGetMediaSubType($0)) }
        let audioOK = audioDescriptions.contains { CMFormatDescriptionGetMediaSubType($0) == kAudioFormatMPEG4AAC }

        return videoOK && audioOK
    }
}
