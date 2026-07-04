import Foundation
import WebKit

@MainActor
final class DownloadBridge: ObservableObject {
    private let licenseClient: LicenseClient
    private let deviceIdentity: DeviceIdentity
    private weak var webView: WKWebView?

    @Published private(set) var isPro: Bool = false
    @Published private(set) var tier: String = "free"

    init(licenseClient: LicenseClient, deviceIdentity: DeviceIdentity) {
        self.licenseClient = licenseClient
        self.deviceIdentity = deviceIdentity
    }

    func attach(webView: WKWebView) {
        self.webView = webView
    }

    // Called once the WKWebView finishes loading iphone_bootstrap.html - sending
    // this any earlier (e.g. right after starting the load) races the page's own
    // script setup and the event can be dropped before window.DownloadThatNative
    // exists to receive it.
    func notifyReady() {
        sendToWeb(event: "nativeReady", payload: [
            "platform": AppConfig.platform,
            "freeDailyDownloadLimit": AppConfig.freeDailyDownloadLimit
        ])
    }

    func handle(message: Any) {
        guard let body = message as? [String: Any], let action = body["action"] as? String else {
            sendToWeb(event: "error", payload: ["message": "Invalid bridge message"])
            return
        }

        switch action {
        case "licenseStatus":
            sendLicenseStatus()
        case "activateLicense":
            let key = body["licenseKey"] as? String ?? ""
            activateLicense(key)
        case "startDownload":
            let url = body["url"] as? String ?? ""
            startDirectURLDownload(url)
        default:
            sendToWeb(event: "error", payload: ["message": "Unsupported action: \(action)"])
        }
    }

    private func sendLicenseStatus() {
        sendToWeb(event: "licenseStatus", payload: ["isPro": isPro, "tier": tier])
    }

    private func activateLicense(_ key: String) {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            sendToWeb(event: "licenseResult", payload: ["valid": false, "reason": "missing_key"])
            return
        }

        Task {
            do {
                let result = try await licenseClient.validate(
                    licenseKey: trimmed,
                    pseudonymousInstallHash: deviceIdentity.hashedInstallId()
                )
                isPro = result.valid && result.deviceAllowed
                tier = result.tier ?? (isPro ? "pro" : "free")
                let reason = !result.valid ? (result.status ?? "invalid") : (!result.deviceAllowed ? "device_limit" : "")
                sendToWeb(event: "licenseResult", payload: [
                    "valid": isPro,
                    "tier": tier,
                    "reason": reason
                ])
            } catch {
                sendToWeb(event: "licenseResult", payload: ["valid": false, "reason": "network_error"])
            }
        }
    }

    // Handles one line of input from the web UI. Plain multi-line batch fan-out (one
    // job per line) happens client-side in iphone_bootstrap.html, matching how
    // web/static/index.html's queueLinks() already does it - so this only ever sees
    // one URL per call. That URL can still expand to many items on its own, though
    // (a YouTube playlist URL resolves to every video it contains via
    // VideoExtractor.expand), which is why this can emit more than one
    // downloadStarted/downloadFinished pair per call.
    private func startDirectURLDownload(_ rawURL: String) {
        let trimmed = rawURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let sourceURL = URL(string: trimmed), ["https", "http"].contains(sourceURL.scheme?.lowercased()) else {
            sendToWeb(event: "downloadFinished", payload: ["ok": false, "url": rawURL, "reason": "invalid_url"])
            return
        }

        Task {
            if VideoExtractor.isKnownHost(sourceURL) {
                await runExtractedDownload(for: sourceURL)
            } else {
                await runPlainDownload(for: sourceURL)
            }
        }
    }

    private func runPlainDownload(for sourceURL: URL) async {
        sendToWeb(event: "downloadStarted", payload: ["url": sourceURL.absoluteString])
        do {
            let savedURL = try await downloadDirectFile(from: sourceURL, suggestedName: nil)
            sendToWeb(event: "downloadFinished", payload: [
                "ok": true,
                "url": sourceURL.absoluteString,
                "fileName": savedURL.lastPathComponent,
                "path": savedURL.path
            ])
        } catch {
            sendToWeb(event: "downloadFinished", payload: [
                "ok": false,
                "url": sourceURL.absoluteString,
                "reason": String(describing: error)
            ])
        }
    }

    // A single input URL can expand into many items (a YouTube playlist) - each
    // expanded item gets its own downloadStarted/downloadFinished pair so the UI can
    // track them independently, the same way a batch of separate lines would.
    private func runExtractedDownload(for sourceURL: URL) async {
        let itemURLs: [URL]
        do {
            itemURLs = try await VideoExtractor.expand(sourceURL)
        } catch {
            sendToWeb(event: "downloadFinished", payload: [
                "ok": false, "url": sourceURL.absoluteString, "reason": "playlist_expand_failed"
            ])
            return
        }

        for itemURL in itemURLs {
            sendToWeb(event: "downloadStarted", payload: ["url": itemURL.absoluteString])
            do {
                let extracted = try await VideoExtractor.resolve(itemURL)
                let (mediaURL, suggestedName, warning): (URL, String?, String?)
                switch extracted {
                case .complete(let url, let name):
                    (mediaURL, suggestedName, warning) = (url, name, nil)
                case .videoOnlyNoAudioYet(let url, let name):
                    (mediaURL, suggestedName, warning) = (url, name, "video_only_no_audio")
                }

                let savedURL = try await downloadDirectFile(from: mediaURL, suggestedName: suggestedName)
                var payload: [String: Any] = [
                    "ok": true,
                    "url": itemURL.absoluteString,
                    "fileName": savedURL.lastPathComponent,
                    "path": savedURL.path
                ]
                if let warning { payload["warning"] = warning }
                sendToWeb(event: "downloadFinished", payload: payload)
            } catch {
                sendToWeb(event: "downloadFinished", payload: [
                    "ok": false, "url": itemURL.absoluteString, "reason": String(describing: error)
                ])
            }
        }
    }

    private func downloadDirectFile(from sourceURL: URL, suggestedName: String?) async throws -> URL {
        let (temporaryURL, response) = try await URLSession.shared.download(from: sourceURL)
        guard let httpResponse = response as? HTTPURLResponse, (200..<300).contains(httpResponse.statusCode) else {
            throw DownloadError.badHTTPStatus
        }

        let documents = try FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )

        let candidateName = suggestedName?.nonEmpty
            ?? response.suggestedFilename?.nonEmpty
            ?? sourceURL.lastPathComponent.nonEmpty
            ?? "download.bin"
        let safeName = candidateName.replacingOccurrences(of: "/", with: "-")
        let destination = uniqueDestinationURL(in: documents, preferredName: safeName)

        if FileManager.default.fileExists(atPath: destination.path) {
            try FileManager.default.removeItem(at: destination)
        }
        try FileManager.default.moveItem(at: temporaryURL, to: destination)
        return destination
    }

    private func uniqueDestinationURL(in folder: URL, preferredName: String) -> URL {
        let base = (preferredName as NSString).deletingPathExtension
        let ext = (preferredName as NSString).pathExtension
        var candidate = folder.appendingPathComponent(preferredName)
        var index = 2
        while FileManager.default.fileExists(atPath: candidate.path) {
            let name = ext.isEmpty ? "\(base)-\(index)" : "\(base)-\(index).\(ext)"
            candidate = folder.appendingPathComponent(name)
            index += 1
        }
        return candidate
    }

    private func sendToWeb(event: String, payload: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let json = String(data: data, encoding: .utf8) else { return }
        let script = "window.DownloadThatNative && window.DownloadThatNative.receive('\(event)', \(json));"
        webView?.evaluateJavaScript(script)
    }
}

private enum DownloadError: Error {
    case badHTTPStatus
}

private extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
