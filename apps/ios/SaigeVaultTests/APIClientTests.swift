import XCTest
@testable import SaigeVault

/// Intercepts requests made by an ephemeral URLSession.
final class StubURLProtocol: URLProtocol {
    typealias Handler = @Sendable (URLRequest) -> (Int, Data)
    nonisolated(unsafe) static var handler: Handler?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.handler, let url = request.url else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        let (status, body) = handler(request)
        let response = HTTPURLResponse(
            url: url, statusCode: status, httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

final class APIClientTests: XCTestCase {
    private var client: APIClient!

    override func setUp() {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubURLProtocol.self]
        client = APIClient(
            baseURL: URL(string: "http://api.test")!,
            session: URLSession(configuration: configuration)
        )
    }

    override func tearDown() {
        StubURLProtocol.handler = nil
    }

    func testDecodesReadinessIncludingSnakeCase() async throws {
        StubURLProtocol.handler = { request in
            XCTAssertEqual(request.url?.path(), "/ready")
            XCTAssertEqual(request.value(forHTTPHeaderField: "X-Request-ID")?.count, 32)
            return (200, Data("""
            {"status":"degraded","version":"0.1.0","environment":"development","checks":[
              {"name":"database","status":"ok","critical":true,"latency_ms":3.2,"detail":"schema=0001"},
              {"name":"qdrant","status":"fail","critical":false,"latency_ms":2000,"detail":"timeout"}
            ]}
            """.utf8))
        }
        let readiness = try await client.readiness()
        XCTAssertEqual(readiness.status, .degraded)
        XCTAssertEqual(readiness.checks.first?.latencyMs, 3.2)
        XCTAssertEqual(readiness.checks.last?.status, .fail)
    }

    func testReadinessBodyIsReturnedOn503() async throws {
        StubURLProtocol.handler = { _ in
            (503, Data(#"{"status":"not_ready","version":"0.1.0","environment":"test","checks":[]}"#.utf8))
        }
        let readiness = try await client.readiness()
        XCTAssertEqual(readiness.status, .notReady)
    }

    func testServerErrorEnvelopeIsSurfaced() async {
        StubURLProtocol.handler = { _ in
            (404, Data(#"{"error":{"code":"not_found","message":"File not found","request_id":"abc"}}"#.utf8))
        }
        do {
            let _: SystemInfo = try await client.systemInfo()
            XCTFail("expected an error")
        } catch {
            XCTAssertEqual(
                error,
                .server(status: 404, code: "not_found", message: "File not found", requestId: "abc")
            )
        }
    }

    func testDecodesSystemInfo() async throws {
        StubURLProtocol.handler = { _ in
            (200, Data("""
            {"version":"0.1.0","environment":"development","api_version":"v1",
             "ai_processing_policy":"local_only","google_oauth_configured":false}
            """.utf8))
        }
        let info = try await client.systemInfo()
        XCTAssertEqual(info.aiProcessingPolicy, .localOnly)
        XCTAssertFalse(info.googleOauthConfigured)
    }
}
