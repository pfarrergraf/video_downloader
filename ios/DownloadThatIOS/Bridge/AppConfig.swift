import Foundation

enum AppConfig {
    static let licenseAPIBase = URL(string: "https://downloadthat.pages.dev")!
    static let platform = "ios"
    static let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.0.0-dev"
    static let freeDailyDownloadLimit = 3
}
