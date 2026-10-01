import SwiftUI

struct HomeView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var pendingFeature: Feature?

    private struct QuickAction: Identifiable {
        let id: String
        let title: String
        let systemImage: String
        let feature: Feature
    }

    private let quickActions: [QuickAction] = [
        .init(id: "upload", title: "Upload", systemImage: "arrow.up.doc", feature: .upload),
        .init(id: "scan", title: "Scan document", systemImage: "doc.viewfinder", feature: .scanner),
        .init(id: "photo", title: "Take photo", systemImage: "camera", feature: .upload),
        .init(id: "ask", title: "Ask AI", systemImage: "sparkles", feature: .askSaige),
        .init(id: "search", title: "Search", systemImage: "magnifyingglass", feature: .search),
        .init(id: "recent", title: "Recent files", systemImage: "clock", feature: .files),
    ]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 10)], spacing: 10) {
                        ForEach(quickActions) { action in
                            Button {
                                pendingFeature = action.feature
                            } label: {
                                VStack(spacing: 8) {
                                    Image(systemName: action.systemImage)
                                        .font(.title3)
                                        .foregroundStyle(Color.accentColor)
                                    Text(action.title)
                                        .font(.caption.weight(.medium))
                                        .foregroundStyle(.primary)
                                        .multilineTextAlignment(.center)
                                }
                                .frame(maxWidth: .infinity, minHeight: 72)
                                .background(
                                    Color(.secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 12, style: .continuous)
                                )
                            }
                            .buttonStyle(.plain)
                            .accessibilityHint("Available in phase \(action.feature.phase)")
                        }
                    }
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
                } header: {
                    Text("Quick actions")
                }

                Section("Server") {
                    ServerStatusRows()
                }

                Section("Set up your vault") {
                    SetupRow(
                        title: "Server reachable",
                        detail: environment.systemInfo.map { "Saige API v\($0.version) (\($0.environment))" }
                            ?? environment.readinessSummary.summary,
                        done: environment.systemInfo != nil
                    )
                    SetupRow(
                        title: "Google OAuth configured",
                        detail: environment.systemInfo?.googleOauthConfigured == true
                            ? "Client credentials are set on the server."
                            : "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on the server.",
                        done: environment.systemInfo?.googleOauthConfigured == true
                    )
                    SetupRow(title: "Sign in", detail: Feature.auth.summary, done: false, feature: .auth)
                    SetupRow(
                        title: "Connect Google Drive",
                        detail: Feature.googleDrive.summary,
                        done: false,
                        feature: .googleDrive
                    )
                }

                Section {
                    FeatureNoticeView(feature: .files)
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.clear)
                }
            }
            .navigationTitle("Saige Vault")
            .refreshable { await environment.refresh() }
            .task { await environment.refresh() }
            .featureAlert($pendingFeature)
        }
    }
}

struct ServerStatusRows: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        let summary = environment.readinessSummary
        HStack(spacing: 10) {
            StatusDot(tone: summary.tone)
            VStack(alignment: .leading, spacing: 2) {
                Text(summary.label).font(.subheadline.weight(.semibold))
                Text(environment.configError?.localizedDescription ?? summary.summary)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if environment.isRefreshing { ProgressView() }
        }
        .accessibilityElement(children: .combine)

        if let readiness = environment.readiness {
            ForEach(readiness.checks) { check in
                HStack {
                    StatusDot(tone: check.status == .ok ? .ok : (check.critical ? .fail : .warn))
                    Text(ReadinessSummary.dependencyLabels[check.name] ?? check.name)
                        .font(.subheadline)
                    if !check.critical {
                        Text("optional").font(.caption2).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(check.status == .ok ? "\(Int(check.latencyMs)) ms" : (check.detail ?? "failed"))
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

private struct SetupRow: View {
    let title: String
    let detail: String
    let done: Bool
    var feature: Feature?

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: done ? "checkmark.circle.fill" : (feature != nil ? "circle.dashed" : "circle"))
                .foregroundStyle(done ? Color.green : Color.secondary)
                .accessibilityLabel(done ? "Done" : "To do")
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.subheadline.weight(.medium))
                Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            Spacer(minLength: 0)
            if let feature { PhaseBadge(feature: feature) }
        }
    }
}
