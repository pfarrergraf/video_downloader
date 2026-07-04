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
            startDownload(url)
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
                isPro = result.valid
                tier = result.tier ?? (result.valid ? "pro" : "free")
                sendToWeb(event: "licenseResult", payload: [
                    "valid": result.valid,
                    "tier": tier,
                    "reason": result.reason ?? ""
                ])
            } catch {
                sendToWeb(event: "licenseResult", payload: ["valid": false, "reason": "network_error"])
            }
        }
    }

    private func startDownload(_ url: String) {
        // Milestone 1: intentionally a stub. Do not port the desktop/Android yt-dlp
        // workflow into iOS until distribution and App Review strategy are decided.
        sendToWeb(event: "downloadRejected", payload: [
            "url": url,
            "reason": "ios_download_engine_not_enabled_yet"
        ])
    }

    private func sendToWeb(event: String, payload: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let json = String(data: data, encoding: .utf8) else { return }
        let script = "window.DownloadThatNative && window.DownloadThatNative.receive('\(event)', \(json));"
        webView?.evaluateJavaScript(script)
    }
}
