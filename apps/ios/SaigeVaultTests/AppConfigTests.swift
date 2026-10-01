import XCTest
@testable import SaigeVault

final class AppConfigTests: XCTestCase {
    func testAcceptsHTTPSURL() throws {
        let config = try AppConfig(rawBaseURL: "https://vault.example.com", requireHTTPS: true)
        XCTAssertEqual(config.apiBaseURL.absoluteString, "https://vault.example.com")
    }

    func testAllowsHTTPWhenNotRequired() throws {
        let config = try AppConfig(rawBaseURL: " http://localhost:8000 ", requireHTTPS: false)
        XCTAssertEqual(config.apiBaseURL.host(), "localhost")
    }

    func testRejectsHTTPInRelease() {
        XCTAssertThrowsError(try AppConfig(rawBaseURL: "http://vault.example.com", requireHTTPS: true)) {
            XCTAssertEqual($0 as? AppConfigError, .insecureBaseURL("http://vault.example.com"))
        }
    }

    func testRejectsEmptyAndMalformed() {
        XCTAssertThrowsError(try AppConfig(rawBaseURL: "", requireHTTPS: false)) {
            XCTAssertEqual($0 as? AppConfigError, .missingBaseURL)
        }
        XCTAssertThrowsError(try AppConfig(rawBaseURL: "ftp://example.com", requireHTTPS: false))
        XCTAssertThrowsError(try AppConfig(rawBaseURL: "not a url", requireHTTPS: false))
    }
}
