import SwiftUI

struct AskView: View {
    @Environment(AppEnvironment.self) private var environment
    @State private var draft = ""
    @State private var pendingFeature: Feature?
    @FocusState private var composerFocused: Bool

    private let suggestions = [
        "What certificates do I have?",
        "When did I join my current company?",
        "What was my net salary in August?",
        "Which documents mention JMeter?",
        "Find documents expiring soon",
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    VStack(spacing: 8) {
                        LogoMark(size: 48)
                        Text("Ask about one document, a collection, or your entire vault. Every answer cites its sources.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 12)

                    if environment.systemInfo?.aiProcessingPolicy == .disabled {
                        Label {
                            Text("AI processing is disabled on this server. No document content is sent to any model.")
                                .font(.footnote)
                        } icon: {
                            Image(systemName: "exclamationmark.shield").foregroundStyle(.orange)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                    }

                    VStack(spacing: 8) {
                        ForEach(suggestions, id: \.self) { suggestion in
                            Button {
                                draft = suggestion
                                composerFocused = true
                            } label: {
                                Text(suggestion)
                                    .font(.subheadline)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(12)
                                    .background(
                                        Color(.secondarySystemBackground),
                                        in: RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    )
                            }
                            .buttonStyle(.plain)
                        }
                    }

                    TrustModelView()
                    FeatureNoticeView(feature: .askSaige)
                }
                .padding()
            }
            .scrollDismissesKeyboard(.interactively)
            .safeAreaInset(edge: .bottom) { composer }
            .navigationTitle("Ask Saige")
            .navigationBarTitleDisplayMode(.inline)
            .featureAlert($pendingFeature)
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField("Ask anything about your documents…", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .focused($composerFocused)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 18))
            Button {
                pendingFeature = .askSaige
            } label: {
                Image(systemName: "arrow.up.circle.fill").font(.system(size: 32))
            }
            .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
            .accessibilityLabel("Send question")
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(.bar)
    }
}

/// Every answer is labelled as one of these — never presented as fact without a source.
private struct TrustModelView: View {
    private struct Kind: Identifiable {
        let icon: String
        let title: String
        let detail: String
        var id: String { title }
    }

    private let kinds: [Kind] = [
        Kind(icon: "checkmark.seal", title: "Source-backed fact", detail: "Quoted from a document, with a page citation."),
        Kind(icon: "lightbulb", title: "AI inference", detail: "Reasoned from sources and labelled as such."),
        Kind(icon: "questionmark.circle", title: "Unknown", detail: "Not in your documents — Saige says so instead of guessing."),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(kinds) { kind in
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: kind.icon).foregroundStyle(Color.accentColor).frame(width: 20)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(kind.title).font(.subheadline.weight(.medium))
                        Text(kind.detail).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(.quaternary)
        )
    }
}
