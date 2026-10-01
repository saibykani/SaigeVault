import SwiftUI

struct SearchView: View {
    enum Mode: String, CaseIterable, Identifiable {
        case hybrid = "Hybrid"
        case fullText = "Full text"
        case semantic = "Semantic"
        case exact = "Exact"
        var id: String { rawValue }
    }

    @State private var query = ""
    @State private var mode: Mode = .hybrid
    @State private var submittedQuery: String?

    private let examples = [
        "Find all payslips from 2026",
        "JMeter performance notes",
        "Certificates from my university",
        "Documents expiring this year",
    ]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("Search mode", selection: $mode) {
                        ForEach(Mode.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets())
                }

                if let submittedQuery {
                    Section {
                        ContentUnavailableView(
                            "Search isn't connected yet",
                            systemImage: "magnifyingglass",
                            description: Text("“\(submittedQuery)” was not sent anywhere. Results will appear here once search is available.")
                        )
                    }
                } else {
                    Section("Try searching for") {
                        ForEach(examples, id: \.self) { example in
                            Button(example) { query = example }
                        }
                    }
                }

                Section {
                    FeatureNoticeView(feature: .search)
                    FeatureNoticeView(feature: .semanticSearch)
                }
                .listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)
            }
            .navigationTitle("Search")
            .searchable(text: $query, prompt: "Files, text, or a question")
            .onSubmit(of: .search) {
                let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
                submittedQuery = trimmed.isEmpty ? nil : trimmed
            }
        }
    }
}
