import SwiftUI

struct FilesView: View {
    @State private var pendingFeature: Feature?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    ContentUnavailableView {
                        Label("Your vault is empty", systemImage: "tray")
                    } description: {
                        Text("Once Google Drive is connected, your documents appear here. Originals always stay in your Drive.")
                    }
                    .padding(.top, 40)
                    FeatureNoticeView(feature: .files)
                }
                .padding()
            }
            .navigationTitle("Files")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button("Upload file", systemImage: "arrow.up.doc") { pendingFeature = .upload }
                        Button("Scan document", systemImage: "doc.viewfinder") { pendingFeature = .scanner }
                        Button("New folder", systemImage: "folder.badge.plus") { pendingFeature = .files }
                    } label: {
                        Label("Add", systemImage: "plus")
                    }
                }
            }
            .featureAlert($pendingFeature)
        }
    }
}
