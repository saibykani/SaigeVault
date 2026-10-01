import Foundation
import Observation

/// App-wide dependencies and shared server state, injected via SwiftUI environment.
@MainActor
@Observable
final class AppEnvironment {
    let configError: AppConfigError?
    let api: APIClient?

    private(set) var readiness: ReadinessResponse?
    private(set) var systemInfo: SystemInfo?
    private(set) var lastRefreshFailed = false
    private(set) var isRefreshing = false

    init(config: Result<AppConfig, AppConfigError>) {
        switch config {
        case .success(let config):
            api = APIClient(baseURL: config.apiBaseURL)
            configError = nil
        case .failure(let error):
            api = nil
            configError = error
        }
    }

    var readinessSummary: ReadinessSummary {
        ReadinessSummary.describe(readiness, failed: lastRefreshFailed || configError != nil)
    }

    func refresh() async {
        guard let api, !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        async let readinessValue = try? api.readiness()
        async let infoValue = try? api.systemInfo()
        readiness = await readinessValue
        systemInfo = await infoValue
        lastRefreshFailed = readiness == nil
    }
}
