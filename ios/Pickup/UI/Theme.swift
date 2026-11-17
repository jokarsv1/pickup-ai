import SwiftUI

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }

    static let ink = Color.accentColor
    static let paper = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.07, green: 0.07, blue: 0.09, alpha: 1) : UIColor(red: 0.97, green: 0.96, blue: 0.945, alpha: 1) })
    static let card = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.12, green: 0.13, blue: 0.15, alpha: 1) : .white })
    static let saffron = Color(hex: 0xF08C00)
    static let liveTint = Color(hex: 0xFFE3C2)
    static let success = Color(hex: 0x2E9E5B)
    static let danger = Color(hex: 0xC62828)
}

struct CategoryStyle {
    var symbol: String
    var color: Color
    var label: String

    static func of(_ category: String?, spam: Bool) -> CategoryStyle {
        if spam || category == "scam" { return CategoryStyle(symbol: "exclamationmark.shield.fill", color: .danger, label: "Likely scam") }
        switch category {
        case "delivery": return CategoryStyle(symbol: "shippingbox.fill", color: .saffron, label: "Delivery")
        case "bank_finance": return CategoryStyle(symbol: "building.columns.fill", color: Color(hex: 0x3D5AFE), label: "Bank")
        case "sales": return CategoryStyle(symbol: "megaphone.fill", color: Color(hex: 0x8E6E53), label: "Sales")
        case "recruiter": return CategoryStyle(symbol: "briefcase.fill", color: Color(hex: 0x00838F), label: "Job")
        case "appointment": return CategoryStyle(symbol: "calendar", color: Color(hex: 0x2E7D32), label: "Appointment")
        case "personal": return CategoryStyle(symbol: "heart.fill", color: Color(hex: 0xD81B60), label: "Personal")
        case "government": return CategoryStyle(symbol: "building.2.fill", color: Color(hex: 0x5D4037), label: "Official")
        default: return CategoryStyle(symbol: "phone.fill", color: .gray, label: "Other")
        }
    }
}

struct CategoryAvatar: View {
    var category: String?
    var spam: Bool
    var size: CGFloat = 44

    var body: some View {
        let style = CategoryStyle.of(category, spam: spam)
        Image(systemName: style.symbol)
            .font(.system(size: size * 0.42, weight: .semibold))
            .foregroundStyle(style.color)
            .frame(width: size, height: size)
            .background(style.color.opacity(0.15), in: Circle())
            .accessibilityHidden(true)
    }
}

struct Pill: View {
    var text: String
    var color: Color

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(color.opacity(0.14), in: Capsule())
    }
}

struct PrimaryButton: View {
    var title: String
    var loading = false
    var enabled = true
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                if loading { ProgressView().tint(.white) } else { Text(title).font(.headline) }
            }
            .frame(maxWidth: .infinity, minHeight: 52)
        }
        .buttonStyle(.borderedProminent)
        .buttonBorderShape(.capsule)
        .disabled(!enabled || loading)
    }
}

struct Bubble: View {
    var speaker: String
    var text: String
    var ownerName: String = "You"

    var body: some View {
        let mine = speaker == "assistant" || speaker == "owner"
        VStack(alignment: mine ? .trailing : .leading, spacing: 4) {
            Text(label).font(.caption).foregroundStyle(.secondary)
            Text(text)
                .padding(12)
                .background(mine ? Color.ink.opacity(0.14) : Color.secondary.opacity(0.14), in: RoundedRectangle(cornerRadius: 18))
        }
        .frame(maxWidth: .infinity, alignment: mine ? .trailing : .leading)
        .padding(mine ? .leading : .trailing, 40)
    }

    private var label: String {
        switch speaker {
        case "assistant": return "Your assistant"
        case "owner": return ownerName
        case "system": return "Note"
        default: return "Caller"
        }
    }
}
