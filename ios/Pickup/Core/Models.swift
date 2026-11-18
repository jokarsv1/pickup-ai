import Foundation

// Mirrors backend/app/schemas.py. JSON keys are snake_case; the API client converts them.
// Timestamps stay ISO-8601 strings and are parsed for display (see Format).

struct PublicConfig: Decodable {
    var authModes: [String] = []
    var devCodeHint: String?
    var voiceReady: Bool = false
    var supportEmail: String?
}

struct User: Codable, Equatable {
    var id: String
    var phone: String
    var name: String?
    var language: String = "en-IN"
    var plan: String = "free"
    var onboardingCompleted: Bool = false
}

struct Tokens: Decodable {
    var accessToken: String
    var refreshToken: String
    var expiresIn: Int
    var user: User
    var isNewUser: Bool
}

struct DevLogin: Encodable { var phone: String; var code: String }
struct RefreshBody: Encodable { var refreshToken: String }
struct MePatch: Encodable { var name: String?; var language: String?; var onboardingCompleted: Bool? }
struct DeviceBody: Encodable { var fcmToken: String; var platform = "ios"; var appVersion: String?; var osVersion: String?; var liveActivityStartToken: String? }
struct LiveActivityTokenBody: Encodable { var token: String }

struct ForwardingCode: Decodable, Identifiable {
    var key: String
    var title: String
    var description: String
    var code: String
    var id: String { key }

    /// The server's wording is written for Android, where Pickup declines calls for you.
    /// On iPhone you decline them yourself.
    var help: String {
        key == "busy" ? "Calls you decline, or that come in while you're on a call, go to your assistant. This is the one that matters most." : description
    }
}

struct Line: Decodable {
    var id: String
    var phone: String
    var assistantNumber: String
    var assistantNumberDisplay: String
    var status: String
    var carrier: String?
    var carrierNote: String?
    var ringSeconds: Int = 20
    var activationCodes: [ForwardingCode] = []
    var deactivationCode: String = "##004#"
    var deactivationAllCode: String = "##002#"
    var isVerified: Bool { status == "verified" }
}

struct LineBody: Encodable { var carrier: String?; var simCount = 1; var ringSeconds = 20 }
struct LinePatch: Encodable { var ringSeconds: Int? }

struct Assistant: Codable {
    var assistantName: String = "Pickup"
    var voice: String = "ritu"
    var languages: [String] = ["en-IN"]
    var instructions: String = ""
    var packIds: [String] = []
    var screeningMode: String = "assistant_first"
    var snoozeUntil: String?
    var recordCalls: Bool = true
    var retentionDays: Int = 90
    var urgentPassthrough: Bool = true
    var deliveryNote: String?
}

struct AssistantPatch: Encodable {
    var voice: String?
    var languages: [String]?
    var instructions: String?
    var packIds: [String]?
    var screeningMode: String?
    var snoozeMinutes: Int?
    var recordCalls: Bool?
    var urgentPassthrough: Bool?
    var deliveryNote: String?
}

struct Pack: Decodable, Identifiable { var id: String; var title: String; var subtitle: String }
struct VoiceOption: Decodable, Identifiable { var id: String; var label: String }

struct AssistantOptions: Decodable {
    var packs: [Pack] = []
    var categories: [String: String] = [:]
    var voices: [VoiceOption] = []
    var languages: [String: String] = [:]
}

struct CallSummary: Decodable, Identifiable, Hashable {
    var id: String
    var direction: String = "inbound"
    var mode: String?
    var state: String
    var title: String
    var callerNumber: String?
    var category: String?
    var categoryLabel: String?
    var reason: String?
    var summary: String?
    var urgency: String?
    var isSpam: Bool = false
    /// TRAI's regulated business numbers: "Verified bank or government number" and so on.
    var callerLabel: String?
    var startedAt: String
    var durationSeconds: Int?
    var unread: Bool = false
    /// A call the carrier never delivered to the assistant.
    var notReached: Bool { mode == "not_reached" }
    var isLive: Bool { ["ringing", "live", "taken_over"].contains(state) }
}

struct TranscriptLine: Decodable, Identifiable, Hashable {
    var seq: Int
    var speaker: String
    var text: String
    var id: Int { seq }
}

struct CallAction: Decodable, Identifiable, Hashable {
    var id: String
    var type: String
    var title: String
    var status: String = "open"
}

struct CallDetail: Decodable, Identifiable {
    var id: String
    var direction: String = "inbound"
    var mode: String?
    var callerLabel: String?
    var state: String
    var title: String
    var callerNumber: String?
    var category: String?
    var categoryLabel: String?
    var reason: String?
    var summary: String?
    var urgency: String?
    var isSpam: Bool = false
    var startedAt: String
    var durationSeconds: Int?
    var suggestedReplies: [String] = []
    var transcript: [TranscriptLine] = []
    var actions: [CallAction] = []
    var rating: Int?
    var isLive: Bool { ["ringing", "live", "taken_over"].contains(state) }
}

struct CallPage: Decodable { var items: [CallSummary] = []; var nextCursor: String? }
struct SupportReportBody: Encodable { var message: String; var diagnostics: [String: String] }
struct SayBody: Encodable { var text: String }
struct FeedbackBody: Encodable { var rating: Int }
struct ActionStatusBody: Encodable { var status: String }

struct Entitlement: Decodable {
    var level: String = "free"
    var liveControls: Bool = false
    var callsLeftThisMonth: Int?
    var trialEndsAt: String?
}

struct Stats: Decodable {
    var callsHandled: Int = 0
    var spamBlocked: Int = 0
    var minutesSaved: Int = 0
}

struct ChatMessage: Decodable, Identifiable, Hashable {
    var id: Int
    var role: String
    var text: String
}

struct ChatBody: Encodable { var text: String }
struct ChatReply: Decodable { var reply: String; var messages: [ChatMessage] = [] }
struct Ticket: Decodable { var ticket: String }
struct Empty: Decodable {}
