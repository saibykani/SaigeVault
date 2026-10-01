import Foundation

enum StatusTone: Sendable, Equatable {
    case ok, warn, fail, unknown
}

/// UI copy for the server's readiness state. Mirrors the web client's
/// describeReadiness() so both clients say the same thing.
struct ReadinessSummary: Sendable, Equatable {
    let tone: StatusTone
    let label: String
    let summary: String

    static let dependencyLabels: [String: String] = [
        "database": "PostgreSQL",
        "redis": "Redis queue",
        "qdrant": "Qdrant vector index",
        "worker": "Background worker",
    ]

    static func describe(_ readiness: ReadinessResponse?, failed: Bool) -> ReadinessSummary {
        if failed {
            return .init(
                tone: .fail,
                label: "Server unreachable",
                summary: "The Saige server could not be reached. Check your connection and server URL."
            )
        }
        guard let readiness else {
            return .init(tone: .unknown, label: "Checking…", summary: "Checking system status.")
        }
        switch readiness.status {
        case .ready:
            return .init(tone: .ok, label: "All systems operational", summary: "Every dependency is healthy.")
        case .degraded:
            let down = readiness.checks.filter { $0.status == .fail }.map(\.name)
            return .init(
                tone: .warn,
                label: "Degraded",
                summary: "Core features work; \(down.joined(separator: ", ")) unavailable."
            )
        case .notReady:
            let down = readiness.checks.filter { $0.status == .fail && $0.critical }.map(\.name)
            return .init(
                tone: .fail,
                label: "Unavailable",
                summary: "Critical dependency down: \(down.joined(separator: ", "))."
            )
        }
    }
}
