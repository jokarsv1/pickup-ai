import ActivityKit
import AppIntents
import SwiftUI
import WidgetKit

@main
struct PickupWidgets: WidgetBundle {
    var body: some Widget {
        CallLiveActivity()
    }
}

struct CallLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: CallActivityAttributes.self) { context in
            LockScreenCallView(callId: context.attributes.callId, state: context.state)
                .padding(16)
                .activityBackgroundTint(Color(uiColor: .systemBackground).opacity(0.92))
                .widgetURL(URL(string: "pickup://live/\(context.attributes.callId)"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: "phone.bubble.fill").font(.title2).foregroundStyle(.blue)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.state == "live" ? "Live" : "Ended").font(.caption.weight(.semibold))
                        .foregroundStyle(context.state.state == "live" ? Color.orange : Color.secondary)
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(context.state.title).font(.headline).lineLimit(1)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(context.state.reason).font(.subheadline).lineLimit(2)
                        if !context.state.lastLine.isEmpty {
                            Text(context.state.lastLine).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                        }
                        if context.state.state == "live" { CallButtons(callId: context.attributes.callId) }
                    }
                }
            } compactLeading: {
                Image(systemName: "phone.fill").foregroundStyle(.green)
            } compactTrailing: {
                Text(context.state.state == "live" ? "Live" : "Done").font(.caption2.weight(.semibold))
            } minimal: {
                Image(systemName: "phone.fill").foregroundStyle(.green)
            }
            .widgetURL(URL(string: "pickup://live/\(context.attributes.callId)"))
        }
    }
}

struct LockScreenCallView: View {
    var callId: String
    var state: CallActivityAttributes.ContentState

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Circle().fill(state.state == "live" ? Color.orange : Color.secondary).frame(width: 8, height: 8)
                Text(state.state == "live" ? "Pickup is on a call" : "Pickup").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            }
            Text(state.title).font(.headline).lineLimit(1)
            Text(state.reason).font(.subheadline).lineLimit(2)
            if !state.lastLine.isEmpty {
                Text(state.lastLine).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            if state.state == "live" { CallButtons(callId: callId) }
        }
    }
}

struct CallButtons: View {
    var callId: String

    var body: some View {
        HStack(spacing: 10) {
            Button(intent: JoinCallIntent(callId: callId)) {
                Label("Join", systemImage: "phone.fill").frame(maxWidth: .infinity)
            }
            .tint(.green)
            Button(intent: EndCallIntent(callId: callId)) {
                Label("End", systemImage: "phone.down.fill").frame(maxWidth: .infinity)
            }
            .tint(.red)
        }
        .buttonStyle(.borderedProminent)
        .font(.subheadline.weight(.semibold))
    }
}
