import Foundation

struct LicenseValidationResult: Codable {
    let valid: Bool
    let tier: String?
    let reason: String?
}

struct LicenseValidationRequest: Codable {
    let licenseKey: String
    let platform: String
    let pseudonymousInstallHash: String
    let appVersion: String

    enum CodingKeys: String, CodingKey {
        case licenseKey = "key"
        case platform
        case pseudonymousInstallHash = "device_hash"
        case appVersion = "app_version"
    }
}

final class LicenseClient {
    private let session: URLSession
    private let apiBase: URL

    init(session: URLSession = .shared, apiBase: URL = AppConfig.licenseAPIBase) {
        self.session = session
        self.apiBase = apiBase
    }

    func validate(licenseKey: String, pseudonymousInstallHash: String) async throws -> LicenseValidationResult {
        let endpoint = apiBase.appending(path: "api").appending(path: "validate")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload = LicenseValidationRequest(
            licenseKey: licenseKey,
            platform: AppConfig.platform,
            pseudonymousInstallHash: pseudonymousInstallHash,
            appVersion: AppConfig.appVersion
        )
        request.httpBody = try JSONEncoder().encode(payload)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<500).contains(http.statusCode) else {
            throw LicenseClientError.invalidResponse
        }
        return try JSONDecoder().decode(LicenseValidationResult.self, from: data)
    }
}

enum LicenseClientError: Error {
    case invalidResponse
}
