import SwiftUI

struct SettingsView: View {
    @Environment(AppEnvironment.self) private var environment
    @Environment(AppLock.self) private var appLock

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle(
                        "Lock with \(appLock.biometryName)",
                        isOn: Binding(get: { appLock.isEnabled }, set: { appLock.setEnabled($0) })
                    )
                    .disabled(!AppLock.canAuthenticate())
                } header: {
                    Text("Security")
                } footer: {
                    Text(
                        AppLock.canAuthenticate()
                            ? "The vault locks whenever Saige Vault goes to the background. Content is hidden in the app switcher."
                            : "Set a device passcode to enable App Lock."
                    )
                }

                Section {
                    LabeledContent("AI processing", value: environment.systemInfo?.aiProcessingPolicy.label ?? "—")
                } header: {
                    Text("AI & privacy")
                } footer: {
                    Text(
                        (environment.systemInfo?.aiProcessingPolicy.explanation ?? "")
                            + " Your documents are never used to train models, and instructions inside documents are treated as data, never as commands."
                    )
                }

                Section("Storage") {
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Google Drive")
                            Text("Not connected").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        PhaseBadge(feature: .googleDrive)
                    }
                }

                Section("Server") {
                    LabeledContent("URL", value: environment.api?.baseURL.absoluteString ?? "Not configured")
                    LabeledContent("Status", value: environment.readinessSummary.label)
                    LabeledContent("API version", value: environment.systemInfo.map { "v\($0.version)" } ?? "—")
                }

                Section("About") {
                    LabeledContent("App version", value: Bundle.main.appVersion)
                    LabeledContent("Build", value: AppConfig.isDebugBuild ? "Debug" : "Release")
                }
            }
            .navigationTitle("Settings")
        }
    }
}

extension Bundle {
    var appVersion: String {
        let version = object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
        let build = object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"
        return "\(version) (\(build))"
    }
}
