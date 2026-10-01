import XCTest
@testable import SaigeVault

final class ReadinessSummaryTests: XCTestCase {
    private func check(_ name: String, ok: Bool, critical: Bool) -> DependencyStatus {
        DependencyStatus(name: name, status: ok ? .ok : .fail, critical: critical, latencyMs: 1, detail: nil)
    }

    func testUnreachableServer() {
        XCTAssertEqual(ReadinessSummary.describe(nil, failed: true).tone, .fail)
    }

    func testLoading() {
        XCTAssertEqual(ReadinessSummary.describe(nil, failed: false).tone, .unknown)
    }

    func testDegradedNamesFailingDependency() {
        let readiness = ReadinessResponse(
            status: .degraded, version: "0.1.0", environment: "test",
            checks: [check("database", ok: true, critical: true), check("worker", ok: false, critical: false)]
        )
        let summary = ReadinessSummary.describe(readiness, failed: false)
        XCTAssertEqual(summary.tone, .warn)
        XCTAssertTrue(summary.summary.contains("worker"))
    }

    func testNotReadyNamesOnlyCriticalDependencies() {
        let readiness = ReadinessResponse(
            status: .notReady, version: "0.1.0", environment: "test",
            checks: [check("redis", ok: false, critical: true), check("qdrant", ok: false, critical: false)]
        )
        let summary = ReadinessSummary.describe(readiness, failed: false)
        XCTAssertEqual(summary.tone, .fail)
        XCTAssertTrue(summary.summary.contains("redis"))
        XCTAssertFalse(summary.summary.contains("qdrant"))
    }

    func testEveryFeatureHasARoadmapPhase() {
        for feature in Feature.allCases {
            XCTAssertTrue((1...16).contains(feature.phase), "\(feature) phase out of range")
            XCTAssertFalse(feature.summary.isEmpty)
        }
    }
}
