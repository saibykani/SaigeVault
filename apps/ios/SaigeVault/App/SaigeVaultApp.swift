import SwiftUI

@main
struct SaigeVaultApp: App {
    @Environment(\.scenePhase) private var scenePhase
    @State private var environment: AppEnvironment
    @State private var appLock: AppLock

    init() {
        let isUITesting = ProcessInfo.processInfo.arguments.contains("-ui-testing")
        let config: Result<AppConfig, AppConfigError>
        do {
            config = .success(try AppConfig.load())
        } catch {
            config = .failure(error)
        }
        _environment = State(initialValue: AppEnvironment(config: config))
        _appLock = State(initialValue: AppLock(forceDisabled: isUITesting))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
                .environment(appLock)
                .tint(Color.accentColor)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { appLock.lock() }
        }
    }
}
