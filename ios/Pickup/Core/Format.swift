import Foundation

/// Display helpers, kept in step with the Android app's Format.kt.
enum Format {
    private static let isoFull: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let isoPlain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    /// Server times are UTC; a time without a zone (older servers) is read as UTC too.
    static func date(_ iso: String?) -> Date? {
        guard var s = iso, !s.isEmpty else { return nil }
        if let d = isoFull.date(from: s) ?? isoPlain.date(from: s) { return d }
        s += "Z"
        return isoFull.date(from: s) ?? isoPlain.date(from: s)
    }

    static func clock(_ iso: String?) -> String {
        guard let d = date(iso) else { return "" }
        return d.formatted(date: .omitted, time: .shortened)
    }

    static func dateTime(_ iso: String?) -> String {
        guard let d = date(iso) else { return "" }
        return d.formatted(.dateTime.day().month(.abbreviated).hour().minute())
    }

    static func dayLabel(_ iso: String?, now: Date = Date(), calendar: Calendar = .current) -> String {
        guard let d = date(iso) else { return "Earlier" }
        if calendar.isDate(d, inSameDayAs: now) { return "Today" }
        if let y = calendar.date(byAdding: .day, value: -1, to: now), calendar.isDate(d, inSameDayAs: y) { return "Yesterday" }
        return d.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated))
    }

    static func duration(_ seconds: Int?) -> String {
        guard let s = seconds, s > 0 else { return "" }
        return s < 60 ? "\(s)s" : "\(s / 60)m \(s % 60)s"
    }

    /// "+919876543210" -> "+91 98765 43210"; landlines -> "+91 22 2654 3210".
    static func phone(_ e164: String?) -> String {
        guard let e164, !e164.isEmpty else { return "" }
        let digits = e164.filter(\.isNumber)
        guard e164.hasPrefix("+91"), digits.count == 12 else { return e164 }
        let n = Array(digits.dropFirst(2))
        let s = { (a: Int, b: Int) in String(n[a..<b]) }
        if let first = n.first, "6789".contains(first) { return "+91 \(s(0, 5)) \(s(5, 10))" }
        return "+91 \(s(0, 2)) \(s(2, 6)) \(s(6, 10))"
    }

    /// Accepts "98765 43210", "09876543210" or "+91 98765-43210"; returns E.164 or nil.
    static func indianMobile(_ input: String) -> String? {
        var digits = input.filter(\.isNumber)
        if digits.count == 12, digits.hasPrefix("91") { digits.removeFirst(2) }
        if digits.count == 11, digits.hasPrefix("0") { digits.removeFirst() }
        guard digits.count == 10, let first = digits.first, "6789".contains(first) else { return nil }
        return "+91" + digits
    }

    static func greeting(hour: Int) -> String {
        switch hour {
        case 5..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    static func firstName(_ name: String?) -> String {
        name?.split(separator: " ").first.map(String.init) ?? ""
    }
}
