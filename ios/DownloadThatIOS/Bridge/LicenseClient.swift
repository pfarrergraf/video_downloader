import Foundation

// Mirrors the response shape of pro/website/functions/api/validate.js, a
// Cloudflare Pages Function shared by every platform (Android, desktop, iOS).
// A license key that doesn't exist responds with just `{"valid": false}`, so
// every field besides `valid` must tolerate being absent from the payload.
struct LicenseValidationResult {
    let valid: Bool
    let tier: String?
    let status: String?
    let deviceAllowed: Bool
}

extension LicenseValidationResult: Decodable {
    private enum CodingKeys: String, CodingKey {
        case valid
        case tier
        case status
        case deviceAllowed = "device_allowed"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        valid = try container.decode(Bool.self, forKey: .valid)
        tier = try container.decodeIfPresent(String.self, forKey: .tier)
        status = try container.decodeIfPresent(String.self, forKey: .status)
        deviceAllowed = try container.decodeIfPresent(Bool.self, forKey: .deviceAllowed) ?? true
    }
}

final class LicenseClient {
    private let session: URLSession
    private let apiBase: URL

    init(session: URLSession = .shared, apiBase: URL = AppConfig.licenseAPIBase) {
        self.session = session
        self.apiBase = apiBase
    }

    // The endpoint is GET /api/validate?key=...&platform=...&device_id=...&app_version=...
    // (see validate.js: it only exports onRequestGet). `device_id` here is
    // already a SHA256 hash, never the raw per-install identifier - the
    // server hashes whatever it receives again before storing it, so this
    // just adds an extra layer of indirection rather than breaking device-slot
    // tracking.
    func validate(licenseKey: String, pseudonymousInstallHash: String) async throws -> LicenseValidationResult {
        guard var components = URLComponents(url: apiBase, resolvingAgainstBaseURL: false) else {
            throw LicenseClientError.invalidResponse
        }
        components.path = "/api/validate"
        components.queryItems = [
            URLQueryItem(name: "key", value: licenseKey),
            URLQueryItem(name: "platform", value: AppConfig.platform),
            URLQueryItem(name: "device_id", value: pseudonymousInstallHash),
            URLQueryItem(name: "app_version", value: AppConfig.appVersion)
        ]
        guard let endpoint = components.url else {
            throw LicenseClientError.invalidResponse
        }

        var request = URLRequest(url: endpoint)
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw LicenseClientError.invalidResponse
        }
        return try JSONDecoder().decode(LicenseValidationResult.self, from: data)
    }
}

enum LicenseClientError: Error {
    case invalidResponse
}
