import Foundation
import LocalAuthentication
import Observation

/// Face ID / Touch ID / passcode lock for the whole app.
///
/// The vault locks when the app goes to the background and requires device
/// owner authentication to reopen. Only the on/off preference is stored
/// (UserDefaults) — no secrets.
@MainActor
@Observable
final class AppLock {
    static let enabledKey = "saige.appLock.enabled"

    private(set) var isEnabled: Bool
    private(set) var isLocked: Bool
    private(set) var lastError: String?

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard, forceDisabled: Bool = false) {
        self.defaults = defaults
        // Locked by default on a fresh install: these are sensitive documents.
        let enabled = forceDisabled ? false : (defaults.object(forKey: Self.enabledKey) as? Bool ?? true)
        isEnabled = enabled
        isLocked = enabled && Self.canAuthenticate()
    }

    var biometryName: String {
        let context = LAContext()
        _ = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
        switch context.biometryType {
        case .faceID: return "Face ID"
        case .touchID: return "Touch ID"
        case .opticID: return "Optic ID"
        default: return "Passcode"
        }
    }

    func setEnabled(_ enabled: Bool) {
        isEnabled = enabled
        defaults.set(enabled, forKey: Self.enabledKey)
        if !enabled { isLocked = false }
    }

    func lock() {
        guard isEnabled, Self.canAuthenticate() else { return }
        isLocked = true
    }

    func unlock() async {
        let context = LAContext()
        context.localizedCancelTitle = "Cancel"
        do {
            // deviceOwnerAuthentication = biometrics with passcode fallback.
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: "Unlock your Saige Vault"
            )
            if success {
                isLocked = false
                lastError = nil
            }
        } catch {
            lastError = "Authentication failed. Try again."
        }
    }

    /// No passcode set (or Simulator without enrolment): locking would strand the user.
    static func canAuthenticate() -> Bool {
        LAContext().canEvaluatePolicy(.deviceOwnerAuthentication, error: nil)
    }
}
