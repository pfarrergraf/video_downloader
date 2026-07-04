import CryptoKit
import Foundation
import Security

final class DeviceIdentity {
    private let service: String
    private let account = "install-id"

    init(service: String = Bundle.main.bundleIdentifier ?? "com.gaistreich.downloadthat.ios") {
        self.service = service
    }

    func hashedInstallId() -> String {
        let raw = installId()
        let digest = SHA256.hash(data: Data(raw.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private func installId() -> String {
        if let existing = readFromKeychain() {
            return existing
        }

        let created = UUID().uuidString
        saveToKeychain(created)
        return created
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
    }

    private func readFromKeychain() -> String? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func saveToKeychain(_ value: String) {
        let data = Data(value.utf8)
        var addQuery = baseQuery()
        addQuery[kSecValueData as String] = data
        addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly

        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
        if addStatus == errSecDuplicateItem {
            let updateQuery = baseQuery()
            let attributes: [String: Any] = [kSecValueData as String: data]
            SecItemUpdate(updateQuery as CFDictionary, attributes as CFDictionary)
        }
    }
}
