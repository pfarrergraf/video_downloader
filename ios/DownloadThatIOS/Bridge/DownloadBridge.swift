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

    private func startDirectURLDownload(_ rawURL: String) {
        let trimmed = rawURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let sourceURL = URL(string: trimmed), ["https", "http"].contains(sourceURL.scheme?.lowercased()) else {
            sendToWeb(event: "downloadFinished", payload: ["ok": false, "reason": "invalid_url"])
            return
        }

        sendToWeb(event: "downloadStarted", payload: ["url": sourceURL.absoluteString])

        Task {
            do {
                let savedURL = try await downloadDirectFile(from: sourceURL)
                sendToWeb(event: "downloadFinished", payload: [
                    "ok": true,
                    "fileName": savedURL.lastPathComponent,
                    "path": savedURL.path
                ])
            } catch {
                sendToWeb(event: "downloadFinished", payload: [
                    "ok": false,
                    "reason": String(describing: error)
                ])
            }
        }
    }

    private func downloadDirectFile(from sourceURL: URL) async throws -> URL {
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

        let suggestedName = response.suggestedFilename?.nonEmpty ?? sourceURL.lastPathComponent.nonEmpty ?? "download.bin"
        let safeName = suggestedName.replacingOccurrences(of: "/", with: "-")
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
