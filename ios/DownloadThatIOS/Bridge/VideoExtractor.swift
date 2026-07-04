import Foundation
import YouTubeKit

/// A single directly-downloadable media reference resolved from a source page URL
/// (YouTube/Vimeo/Reddit watch page, etc.) - separate from the existing
/// URLSession-based downloader in DownloadBridge, which just needs a URL to fetch.
enum ExtractedItem {
    /// A ready-to-download file that already has audio (progressive/muxed stream, or
    /// a site that only ever serves single files).
    case complete(url: URL, suggestedName: String?)
    /// Video and (optionally) audio as two separate streams with no merge available
    /// yet (see AVFoundation passthrough remux, tracked separately). `audio` is nil
    /// when the source genuinely has no audio track (e.g. a silent clip) rather than
    /// merge support being missing - callers should still surface "not merged" plainly
    /// when audio is present, since two separate files isn't what the user asked for.
    case separateVideoAudio(video: URL, audio: URL?, suggestedVideoName: String?, suggestedAudioName: String?)
}

enum VideoExtractorError: Error {
    case unsupportedHost
    case noPlayableStream
    case malformedResponse
}

/// Resolves source page URLs (YouTube, Vimeo, Reddit) into direct, downloadable media
/// URLs. No embedded Python/yt-dlp - see ios/README.md's "Download engine" section for
/// why. YouTube goes through YouTubeKit (JavaScriptCore-backed cipher/n-parameter
/// solving); Vimeo and Reddit are plain native JSON/manifest parsing with no cipher or
/// auth needed for public content.
enum VideoExtractor {

    static func isKnownHost(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return isYouTubeHost(host) || isVimeoHost(host) || isRedditHost(host)
    }

    /// Expands a URL that may reference a collection (a YouTube playlist) into the
    /// individual item URLs it contains. Non-playlist URLs expand to just themselves -
    /// this is also what makes plain multi-line batch input work without a separate
    /// code path, matching how the shared web UI already treats batch as client-side
    /// fan-out (one job per line) rather than a server-side concept.
    ///
    /// `allowPlaylist` mirrors web/server.py's `allow_playlist = ... and is_pro`: a
    /// playlist is effectively unlimited downloads behind a single URL, so free-tier
    /// callers pass `false` and get just the single input URL back rather than every
    /// video the playlist contains.
    static func expand(_ url: URL, allowPlaylist: Bool) async throws -> [URL] {
        guard allowPlaylist,
              let host = url.host?.lowercased(), isYouTubeHost(host),
              let playlistID = youTubePlaylistID(in: url) else {
            return [url]
        }
        return try await expandYouTubePlaylist(playlistID: playlistID)
    }

    /// Resolves a single item URL (never a playlist - call `expand` first) to a
    /// directly downloadable stream.
    static func resolve(_ url: URL) async throws -> ExtractedItem {
        guard let host = url.host?.lowercased() else { throw VideoExtractorError.unsupportedHost }
        if isYouTubeHost(host) {
            return try await resolveYouTube(url: url)
        }
        if isVimeoHost(host) {
            return try await resolveVimeo(url: url)
        }
        if isRedditHost(host) {
            return try await resolveReddit(url: url)
        }
        throw VideoExtractorError.unsupportedHost
    }

    // MARK: - YouTube

    private static func isYouTubeHost(_ host: String) -> Bool {
        host == "youtube.com" || host.hasSuffix(".youtube.com") || host == "youtu.be"
    }

    private static func youTubeVideoID(from url: URL) -> String? {
        let host = url.host?.lowercased() ?? ""
        if host == "youtu.be" {
            let id = url.pathComponents.last(where: { $0 != "/" })
            return id
        }
        if let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
           let queryID = components.queryItems?.first(where: { $0.name == "v" })?.value,
           !queryID.isEmpty {
            return queryID
        }
        // /shorts/<id> and /embed/<id>
        let parts = url.pathComponents.filter { $0 != "/" }
        if let index = parts.firstIndex(where: { $0 == "shorts" || $0 == "embed" }), index + 1 < parts.count {
            return parts[index + 1]
        }
        return nil
    }

    private static func youTubePlaylistID(in url: URL) -> String? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return nil }
        return components.queryItems?.first(where: { $0.name == "list" })?.value
    }

    private static func resolveYouTube(url: URL) async throws -> ExtractedItem {
        guard let videoID = youTubeVideoID(from: url) else { throw VideoExtractorError.unsupportedHost }

        // .local only, deliberately: the .remote fallback YouTubeKit offers routes
        // extraction through a third-party-hosted (or self-hosted) youtube-dl server
        // over a WebSocket. Defaulting to that would silently send URLs to a server
        // we don't control, which conflicts with this app's "no hidden network
        // dependency" stance - see docs/IPHONE_APP_PLAN.md.
        let video = YouTube(videoID: videoID, methods: [.local])
        let streams = try await video.streams

        if let progressive = streams
            .filterVideoAndAudio()
            .filter({ $0.isNativelyPlayable })
            .highestResolutionStream() {
            return .complete(
                url: progressive.url,
                suggestedName: suggestedFileName(id: videoID, fileExtension: progressive.fileExtension)
            )
        }

        // No pre-muxed stream at a usable quality - fall back to separate video/audio
        // streams rather than failing outright. Merging them isn't implemented yet
        // (AVFoundation passthrough remux, tracked separately).
        guard let videoOnly = streams.filterVideoOnly().highestResolutionStream() else {
            throw VideoExtractorError.noPlayableStream
        }
        let audioOnly = streams.filterAudioOnly().highestAudioBitrateStream()
        return .separateVideoAudio(
            video: videoOnly.url,
            audio: audioOnly?.url,
            suggestedVideoName: suggestedFileName(id: videoID, fileExtension: videoOnly.fileExtension),
            suggestedAudioName: audioOnly.map { suggestedFileName(id: "\(videoID)-audio", fileExtension: $0.fileExtension) }
        )
    }

    private static func expandYouTubePlaylist(playlistID: String) async throws -> [URL] {
        guard let endpoint = URL(string: "https://www.youtube.com/youtubei/v1/browse") else {
            throw VideoExtractorError.malformedResponse
        }
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "context": ["client": ["clientName": "WEB", "clientVersion": "2.20240101.00.00"]],
            "browseId": "VL" + playlistID,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw VideoExtractorError.malformedResponse
        }
        guard let text = String(data: data, encoding: .utf8) else {
            throw VideoExtractorError.malformedResponse
        }

        let videoIDs = extractAll(pattern: "\"videoId\":\"([a-zA-Z0-9_-]{11})\"", in: text)
        guard !videoIDs.isEmpty else { throw VideoExtractorError.noPlayableStream }
        return videoIDs.compactMap { URL(string: "https://www.youtube.com/watch?v=\($0)") }
    }

    // MARK: - Vimeo

    private static func isVimeoHost(_ host: String) -> Bool {
        host == "vimeo.com" || host.hasSuffix(".vimeo.com")
    }

    private static func vimeoVideoID(from url: URL) -> String? {
        url.pathComponents.first { $0.count >= 6 && $0.allSatisfy(\.isNumber) }
    }

    private struct VimeoConfig: Decodable {
        struct Request: Decodable {
            struct Files: Decodable {
                struct Progressive: Decodable {
                    let url: URL
                    let width: Int?
                    let height: Int?
                }
                let progressive: [Progressive]?
            }
            let files: Files
        }
        let request: Request
    }

    private static func resolveVimeo(url: URL) async throws -> ExtractedItem {
        guard let videoID = vimeoVideoID(from: url),
              let configURL = URL(string: "https://player.vimeo.com/video/\(videoID)/config") else {
            throw VideoExtractorError.unsupportedHost
        }

        let (data, response) = try await URLSession.shared.data(from: configURL)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw VideoExtractorError.malformedResponse
        }

        let config = try JSONDecoder().decode(VimeoConfig.self, from: data)
        // Long videos are DASH-only (no progressive rendition) on Vimeo - out of scope
        // for now, same reasoning as skipping ffmpeg/DASH-manifest work elsewhere.
        guard let best = config.request.files.progressive?.max(by: { ($0.height ?? 0) < ($1.height ?? 0) }) else {
            throw VideoExtractorError.noPlayableStream
        }
        return .complete(url: best.url, suggestedName: "\(videoID).mp4")
    }

    // MARK: - Reddit

    private static func isRedditHost(_ host: String) -> Bool {
        host == "reddit.com" || host.hasSuffix(".reddit.com")
    }

    private struct RedditListing: Decodable {
        struct Child: Decodable {
            struct Data: Decodable {
                struct SecureMedia: Decodable {
                    struct RedditVideo: Decodable {
                        let fallbackURL: URL
                        enum CodingKeys: String, CodingKey { case fallbackURL = "fallback_url" }
                    }
                    let redditVideo: RedditVideo?
                    enum CodingKeys: String, CodingKey { case redditVideo = "reddit_video" }
                }
                let secureMedia: SecureMedia?
                enum CodingKeys: String, CodingKey { case secureMedia = "secure_media" }
            }
            let data: Data
        }
        struct Listing: Decodable {
            let children: [Child]
        }
        let data: Listing
    }

    private static func resolveReddit(url: URL) async throws -> ExtractedItem {
        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            throw VideoExtractorError.malformedResponse
        }
        components.host = "www.reddit.com"
        components.path = components.path.hasSuffix("/") ? components.path + ".json" : components.path + "/.json"
        guard let jsonURL = components.url else { throw VideoExtractorError.malformedResponse }

        var request = URLRequest(url: jsonURL)
        request.setValue("DownloadThatIOS/1.0", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw VideoExtractorError.malformedResponse
        }

        let listings = try JSONDecoder().decode([RedditListing].self, from: data)
        guard let fallbackURL = listings.first?.data.children.first?.data.secureMedia?.redditVideo?.fallbackURL else {
            throw VideoExtractorError.noPlayableStream
        }

        // v.redd.it serves the video track at e.g. https://v.redd.it/<id>/DASH_720.mp4;
        // the matching audio-only track (when the clip has audio at all) conventionally
        // lives alongside it as DASH_audio.mp4. There's no manifest fetch to confirm
        // this ahead of time - DownloadBridge attempts the audio download best-effort
        // and just drops it if that guess doesn't exist (e.g. a silent clip).
        let audioURL = fallbackURL.deletingLastPathComponent().appendingPathComponent("DASH_audio.mp4")
        let baseName = url.pathComponents.last { $0 != "/" } ?? "reddit-video"
        return .separateVideoAudio(
            video: fallbackURL,
            audio: audioURL,
            suggestedVideoName: "\(baseName).mp4",
            suggestedAudioName: "\(baseName)-audio.m4a"
        )
    }

    // MARK: - Shared helpers

    /// Scans raw text for a regex with one capture group, returning distinct matches
    /// in first-seen order. Used instead of modeling exact JSON structure where that
    /// structure is known to reshuffle often (see the YouTube playlist comment above).
    private static func extractAll(pattern: String, in text: String) -> [String] {
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
        let range = NSRange(text.startIndex..., in: text)
        var seen = Set<String>()
        var ordered: [String] = []
        regex.enumerateMatches(in: text, range: range) { match, _, _ in
            guard let match, let idRange = Range(match.range(at: 1), in: text) else { return }
            let value = String(text[idRange])
            if seen.insert(value).inserted {
                ordered.append(value)
            }
        }
        return ordered
    }

    private static func suggestedFileName(id: String, fileExtension: FileExtension) -> String {
        "\(id).\(String(describing: fileExtension))"
    }
}
