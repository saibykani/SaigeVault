import SwiftUI

/// Saige Vault mark: a vault tile enclosing a sage leaf.
struct LogoMark: View {
    var size: CGFloat = 32

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
                .fill(Color.accentColor)
            Image(systemName: "leaf.fill")
                .font(.system(size: size * 0.5, weight: .semibold))
                .foregroundStyle(.white)
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

struct StatusDot: View {
    let tone: StatusTone

    var body: some View {
        Circle()
            .fill(color)
            .frame(width: 8, height: 8)
            .accessibilityHidden(true)
    }

    private var color: Color {
        switch tone {
        case .ok: .green
        case .warn: .orange
        case .fail: .red
        case .unknown: .secondary.opacity(0.5)
        }
    }
}

/// Explains that a capability is not yet built. Never fakes functionality.
struct FeatureNoticeView: View {
    let feature: Feature

    var body: some View {
        if !feature.isAvailable {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "hammer")
                    .foregroundStyle(.secondary)
                    .accessibilityHidden(true)
                Text(feature.notice)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [4]))
                    .foregroundStyle(.quaternary)
            )
            .accessibilityElement(children: .combine)
        }
    }
}

struct PhaseBadge: View {
    let feature: Feature

    var body: some View {
        if !feature.isAvailable {
            Text("P\(feature.phase)")
                .font(.caption2.monospaced().weight(.medium))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 5)
                .padding(.vertical, 2)
                .overlay(Capsule().strokeBorder(.quaternary))
                .accessibilityLabel("Available in phase \(feature.phase)")
        }
    }
}

extension View {
    /// Presents an alert explaining an unavailable feature.
    func featureAlert(_ feature: Binding<Feature?>) -> some View {
        alert(
            feature.wrappedValue.map { "\($0.label) — Phase \($0.phase)" } ?? "",
            isPresented: Binding(
                get: { feature.wrappedValue != nil },
                set: { if !$0 { feature.wrappedValue = nil } }
            ),
            presenting: feature.wrappedValue
        ) { _ in
            Button("OK", role: .cancel) {}
        } message: { f in
            Text("\(f.summary)\n\nNothing was sent or stored.")
        }
    }
}
