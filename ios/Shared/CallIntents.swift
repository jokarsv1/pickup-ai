import AppIntents
import Foundation

// Buttons on the Live Activity. The system runs LiveActivityIntents in the app's process, where
// the API client and the Keychain live; the widget extension only needs the types to draw buttons.

struct JoinCallIntent: LiveActivityIntent {
    static let title: LocalizedStringResource = "Join call"

    @Parameter(title: "Call") var callId: String

    init() {}
    init(callId: String) { self.callId = callId }

    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        let _: Empty? = try? await API.shared.post("/v1/calls/\(callId)/takeover")
        #endif
        return .result()
    }
}

struct EndCallIntent: LiveActivityIntent {
    static let title: LocalizedStringResource = "End call"

    @Parameter(title: "Call") var callId: String

    init() {}
    init(callId: String) { self.callId = callId }

    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        let _: Empty? = try? await API.shared.post("/v1/calls/\(callId)/end")
        #endif
        return .result()
    }
}
