import Foundation
import YouTubeKit

/// A single directly-downloadable media reference resolved from a source page URL
/// (YouTube/Vimeo/Reddit watch page, etc.) - separate from the existing
/// URLSession-based downloader in DownloadBridge, which just needs a URL to fetch.
enum ExtractedItem {
    /// A ready-to-download file that already has audio (progressive/muxed stream, or
    /// a site that only ever serves single files).
    case complete(url: URL, suggestedName: String?)
    /// A video-only stream with no matching audio merge available yet (see
    /// AVFoundation passthrough remux, tracked separately). Downloading this alone
    /// produces a silent video - callers should surface that plainly rather than
    /// silently shipping a broken file.
    case videoOnlyNoAudioYet(url: URL, suggestedName: String?)
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
        return isYouTubeHost(host)
    }

    /// Expands a URL that may reference a collection (a YouTube playlist) into the
    /// individual item URLs it contains. Non-playlist URLs expand to just themselves -
    /// this is also what makes plain multi-line batch input work without a separate
    /// code path, matching how the shared web UI already treats batch as client-side
    /// fan-out (one job per line) rather than a server-side concept.
    static func expand(_ url: URL) async throws -> [URL] {
        guard let host = url.host?.lowercased(), isYouTubeHost(host),
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
                suggestedName: suggestedFileName(videoID: videoID, fileExtension: progressive.fileExtension)
            )
        }

        // No pre-muxed stream at a usable quality - fall back to video-only rather
        // than failing outright. Merging with a separately-downloaded audio track
        // isn't implemented yet (AVFoundation passthrough remux, tracked separately).
        if let videoOnly = streams.filterVideoOnly().highestResolutionStream() {
            return .videoOnlyNoAudioYet(
                url: videoOnly.url,
                suggestedName: suggestedFileName(videoID: videoID, fileExtension: videoOnly.fileExtension)
            )
        }

        throw VideoExtractorError.noPlayableStream
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

        let videoIDs = extractVideoIDs(from: text)
        guard !videoIDs.isEmpty else { throw VideoExtractorError.noPlayableStream }
        return videoIDs.compactMap { URL(string: "https://www.youtube.com/watch?v=\($0)") }
    }

    /// YouTube's internal `browse` response is a deeply nested structure that
    /// reshuffles unrelated fields often enough that modeling the exact path is
    /// brittle. Scanning the raw JSON text for `videoId` occurrences directly is more
    /// resilient - that key name itself has been stable for years even as the
    /// surrounding structure hasn't.
    private static func extractVideoIDs(from jsonText: String) -> [String] {
        guard let regex = try? NSRegularExpression(pattern: "\"videoId\":\"([a-zA-Z0-9_-]{11})\"") else {
            return []
        }
        let range = NSRange(jsonText.startIndex..., in: jsonText)
        var seen = Set<String>()
        var ordered: [String] = []
        regex.enumerateMatches(in: jsonText, range: range) { match, _, _ in
            guard let match, let idRange = Range(match.range(at: 1), in: jsonText) else { return }
            let id = String(jsonText[idRange])
            if seen.insert(id).inserted {
                ordered.append(id)
            }
        }
        return ordered
    }

    private static func suggestedFileName(videoID: String, fileExtension: FileExtension) -> String {
        "\(videoID).\(String(describing: fileExtension))"
    }
}
