import ActivityKit
import Foundation

/// A call your assistant is handling, shown on the Lock Screen and in the Dynamic Island.
/// The server starts, updates and ends it by push; keys must match backend/app/push.py.
struct CallActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var title: String
        var reason: String
        var lastLine: String
        var state: String  // live | ended
    }

    var callId: String
}
