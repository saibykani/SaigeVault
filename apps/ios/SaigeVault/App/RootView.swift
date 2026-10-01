import SwiftUI

struct RootView: View {
    @Environment(\.scenePhase) private var scenePhase
    @Environment(AppLock.self) private var appLock

    var body: some View {
        ZStack {
            if appLock.isLocked {
                LockView()
                    .transition(.opacity)
            } else {
                MainTabView()
            }
            // Hide content in the app switcher snapshot and while inactive.
            if scenePhase != .active {
                PrivacyShield()
                    .transition(.opacity)
            }
        }
        .animation(.easeOut(duration: 0.15), value: appLock.isLocked)
        .animation(.easeOut(duration: 0.15), value: scenePhase)
    }
}

struct MainTabView: View {
    enum Tab: Hashable { case home, files, search, ask, settings }
    @State private var selection: Tab = .home

    var body: some View {
        TabView(selection: $selection) {
            HomeView()
                .tabItem { Label("Home", systemImage: "square.grid.2x2") }
                .tag(Tab.home)
            FilesView()
                .tabItem { Label("Files", systemImage: "folder") }
                .tag(Tab.files)
            SearchView()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }
                .tag(Tab.search)
            AskView()
                .tabItem { Label("Ask Saige", systemImage: "sparkles") }
                .tag(Tab.ask)
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
                .tag(Tab.settings)
        }
    }
}

struct PrivacyShield: View {
    var body: some View {
        ZStack {
            Rectangle().fill(.regularMaterial).ignoresSafeArea()
            LogoMark(size: 64)
        }
        .accessibilityHidden(true)
    }
}
