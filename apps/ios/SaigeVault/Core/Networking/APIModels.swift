import Foundation

// Mirrors the backend OpenAPI schema (docs/api/openapi.json). Keys are
// decoded with .convertFromSnakeCase; enum raw values match the wire format.

struct LivenessResponse: Decodable, Sendable, Equatable {
    let status: String
    let service: String
    let version: String
}

struct DependencyStatus: Decodable, Sendable, Equatable, Identifiable {
    enum Status: String, Decodable, Sendable {
        case ok
        case fail
    }

    let name: String
    let status: Status
    let critical: Bool
    let latencyMs: Double
    let detail: String?

    var id: String { name }
}

struct ReadinessResponse: Decodable, Sendable, Equatable {
    enum Status: String, Decodable, Sendable {
        case ready
        case degraded
        case notReady = "not_ready"
    }

    let status: Status
    let version: String
    let environment: String
    let checks: [DependencyStatus]
}

enum AIProcessingPolicy: String, Decodable, Sendable {
    case disabled
    case localOnly = "local_only"
    case thirdPartyAllowed = "third_party_allowed"

    var label: String {
        switch self {
        case .disabled: "Disabled"
        case .localOnly: "Local models only"
        case .thirdPartyAllowed: "Third-party providers allowed"
        }
    }

    var explanation: String {
        switch self {
        case .disabled: "AI processing is disabled — no document content leaves the server."
        case .localOnly: "AI runs on local models only — content never leaves your deployment."
        case .thirdPartyAllowed: "Third-party AI providers are allowed by server policy."
        }
    }
}

struct SystemInfo: Decodable, Sendable, Equatable {
    let version: String
    let environment: String
    let apiVersion: String
    let aiProcessingPolicy: AIProcessingPolicy
    let googleOauthConfigured: Bool
}

struct APIErrorEnvelope: Decodable, Sendable {
    struct Body: Decodable, Sendable {
        let code: String
        let message: String
        let requestId: String?
    }

    let error: Body
}
