import SwiftUI

struct LockView: View {
    @Environment(AppLock.self) private var appLock
    @State private var isAuthenticating = false

    var body: some View {
        VStack(spacing: 20) {
            Spacer()
            LogoMark(size: 72)
            VStack(spacing: 6) {
                Text("Saige Vault is locked")
                    .font(.title3.weight(.semibold))
                Text("Your documents are protected.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if let error = appLock.lastError {
                Text(error)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
            Button {
                Task { await authenticate() }
            } label: {
                Label("Unlock with \(appLock.biometryName)", systemImage: "lock.open")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(isAuthenticating)
            .padding(.horizontal, 32)
            .padding(.bottom, 40)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
        .task { await authenticate() }
    }

    private func authenticate() async {
        guard !isAuthenticating else { return }
        isAuthenticating = true
        await appLock.unlock()
        isAuthenticating = false
    }
}
