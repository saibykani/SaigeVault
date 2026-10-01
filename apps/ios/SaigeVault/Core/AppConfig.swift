import Foundation

enum AppConfigError: Error, Equatable, LocalizedError {
    case missingBaseURL
    case invalidBaseURL(String)
    case insecureBaseURL(String)

    var errorDescription: String? {
        switch self {
        case .missingBaseURL:
            "No Saige server URL is configured (SaigeAPIBaseURL)."
        case .invalidBaseURL(let raw):
            "The configured server URL is invalid: \(raw)"
        case .insecureBaseURL(let raw):
            "Release builds require an HTTPS server URL: \(raw)"
        }
    }
}

/// Build-time configuration read from Info.plist (populated from xcconfig).
struct AppConfig: Sendable, Equatable {
    static let infoPlistKey = "SaigeAPIBaseURL"

    let apiBaseURL: URL

    init(rawBaseURL: String, requireHTTPS: Bool) throws(AppConfigError) {
        let trimmed = rawBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { throw .missingBaseURL }
        guard
            let url = URL(string: trimmed),
            let scheme = url.scheme?.lowercased(),
            ["http", "https"].contains(scheme),
            url.host() != nil
        else { throw .invalidBaseURL(trimmed) }
        if requireHTTPS, scheme != "https" { throw .insecureBaseURL(trimmed) }
        apiBaseURL = url
    }

    static func load(from bundle: Bundle = .main) throws(AppConfigError) -> AppConfig {
        guard let raw = bundle.object(forInfoDictionaryKey: infoPlistKey) as? String else {
            throw .missingBaseURL
        }
        return try AppConfig(rawBaseURL: raw, requireHTTPS: !isDebugBuild)
    }

    static var isDebugBuild: Bool {
        #if DEBUG
            true
        #else
            false
        #endif
    }
}
