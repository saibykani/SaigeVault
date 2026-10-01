import Foundation

enum APIError: Error, Equatable, LocalizedError {
    case transport(String)
    case invalidResponse
    case server(status: Int, code: String, message: String, requestId: String?)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .transport: "Couldn't reach the Saige server."
        case .invalidResponse: "The server sent an unexpected response."
        case .server(_, _, let message, _): message
        case .decoding: "The server response couldn't be read."
        }
    }
}

/// Thin, typed client for the Saige REST API.
///
/// Uses an ephemeral session: no response caching to disk, so document
/// metadata is not left behind in URL caches.
final class APIClient: Sendable {
    let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = APIClient.makeSession()) {
        self.baseURL = baseURL
        self.session = session
    }

    static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 15
        configuration.httpAdditionalHeaders = ["Accept": "application/json"]
        return URLSession(configuration: configuration)
    }

    func health() async throws(APIError) -> LivenessResponse {
        try await get("health")
    }

    /// Readiness is meaningful on 503 too, so that body is decoded as well.
    func readiness() async throws(APIError) -> ReadinessResponse {
        try await get("ready", acceptedStatuses: [200, 503])
    }

    func systemInfo() async throws(APIError) -> SystemInfo {
        try await get("api/v1/system/info")
    }

    func get<Response: Decodable & Sendable>(
        _ path: String,
        acceptedStatuses: Set<Int> = [200]
    ) async throws(APIError) -> Response {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = "GET"
        request.setValue(Self.newRequestID(), forHTTPHeaderField: "X-Request-ID")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw .transport(String(describing: type(of: error)))
        }
        guard let http = response as? HTTPURLResponse else { throw .invalidResponse }
        let decoder = Self.makeDecoder()

        guard acceptedStatuses.contains(http.statusCode) else {
            if let envelope = try? decoder.decode(APIErrorEnvelope.self, from: data) {
                throw .server(
                    status: http.statusCode,
                    code: envelope.error.code,
                    message: envelope.error.message,
                    requestId: envelope.error.requestId
                )
            }
            throw .server(
                status: http.statusCode,
                code: "http_error",
                message: "Request failed with status \(http.statusCode).",
                requestId: http.value(forHTTPHeaderField: "X-Request-ID")
            )
        }
        do {
            return try decoder.decode(Response.self, from: data)
        } catch {
            throw .decoding(String(describing: type(of: error)))
        }
    }

    static func newRequestID() -> String {
        UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    }
}
