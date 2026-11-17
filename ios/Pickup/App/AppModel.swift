import ActivityKit
import SwiftUI
import UIKit
import UserNotifications

/// App-wide state: who is signed in, which part of the app to show, and live events.
@MainActor
@Observable
final class AppModel {
    static let shared = AppModel()

    enum Phase { case loading, onboarding, main }

    var phase: Phase = .loading
    var user: User?
    /// A call to open, set when the user taps a notification.
    var openCallId: String?
    /// A live call to open, set when the user taps the Live Activity.
    var openLiveCallId: String?
    /// Bumped whenever the server reports a change; screens reload when it moves.
    var liveTick = 0

    private var events: LiveEvents?
    private var pushToken: String?
    private var liveActivityStartToken: String?
    private var observingActivities = false

    func start() async {
        #if DEBUG
        if ProcessInfo.processInfo.environment["UITEST_RESET"] == "1" { await API.shared.signOutLocally() }
        #endif
        guard await API.shared.hasSession else {
            phase = .onboarding
            return
        }
        do {
            let me: User = try await API.shared.get("/v1/me")
            user = me
            phase = me.onboardingCompleted ? .main : .onboarding
        } catch let error as APIError where error.status == 401 {
            await API.shared.signOutLocally()
            phase = .onboarding
        } catch {
            phase = .main // offline: show the app; screens report the error
        }
        if phase == .main { didEnterMain() }
    }

    func signedIn(_ tokens: Tokens) async {
        await API.shared.saveTokens(tokens)
        user = tokens.user
        await registerPushToken()
    }

    func finishOnboarding() {
        phase = .main
        didEnterMain()
    }

    func signOut() async {
        if let refresh = Keychain.get("refresh") {
            let _: Empty? = try? await API.shared.post("/v1/auth/logout", RefreshBody(refreshToken: refresh))
        }
        await API.shared.signOutLocally()
        events?.stop()
        events = nil
        user = nil
        phase = .onboarding
    }

    private func didEnterMain() {
        if events == nil {
            let events = LiveEvents { [weak self] in self?.liveTick += 1 }
            events.start()
            self.events = events
        }
        Task { await requestPushPermissionIfAllowed() }
    }

    // MARK: Push notifications

    func requestPushPermissionIfAllowed() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        if settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    func askForNotifications() async -> Bool {
        let granted = (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        if granted { UIApplication.shared.registerForRemoteNotifications() }
        return granted
    }

    func didReceivePushToken(_ token: String) async {
        pushToken = token
        await registerPushToken()
    }

    private func registerPushToken() async {
        guard let pushToken, await API.shared.hasSession else { return }
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        let body = DeviceBody(fcmToken: pushToken, appVersion: version, osVersion: "iOS \(UIDevice.current.systemVersion)", liveActivityStartToken: liveActivityStartToken)
        let _: Empty? = try? await API.shared.post("/v1/devices", body)
    }

    // MARK: Live Activities (Lock Screen and Dynamic Island)

    /// Hands the server the tokens it needs to start a call's Live Activity, and each activity's
    /// own update token. Runs at launch, including background launches the system makes for this.
    func observeLiveActivities() {
        guard !observingActivities else { return }
        observingActivities = true
        if #available(iOS 17.2, *) {
            Task {
                for await data in Activity<CallActivityAttributes>.pushToStartTokenUpdates {
                    liveActivityStartToken = data.map { String(format: "%02x", $0) }.joined()
                    await registerPushToken()
                }
            }
        }
        Task {
            for await activity in Activity<CallActivityAttributes>.activityUpdates {
                observe(activity)
            }
        }
    }

    private func observe(_ activity: Activity<CallActivityAttributes>) {
        Task {
            for await data in activity.pushTokenUpdates {
                let token = data.map { String(format: "%02x", $0) }.joined()
                let _: Empty? = try? await API.shared.post("/v1/calls/\(activity.attributes.callId)/live-activity", LiveActivityTokenBody(token: token))
            }
        }
    }

    /// pickup://live/<call id> from the Live Activity.
    func handle(url: URL) {
        guard url.scheme == "pickup", url.host == "live" else { return }
        let id = url.lastPathComponent
        if !id.isEmpty, id != "/" { openLiveCallId = id }
    }
}

/// The server's live event stream (WebSocket), used to refresh open screens instantly.
@MainActor
final class LiveEvents {
    private let onEvent: () -> Void
    private var task: URLSessionWebSocketTask?
    private var running = false
    private var backoff: UInt64 = 1

    init(onEvent: @escaping () -> Void) { self.onEvent = onEvent }

    func start() {
        running = true
        Task { await connect() }
    }

    func stop() {
        running = false
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
    }

    private func connect() async {
        while running {
            do {
                let ticket: Ticket = try await API.shared.post("/v1/stream/ticket")
                let base = API.baseURL.replacingOccurrences(of: "https://", with: "wss://").replacingOccurrences(of: "http://", with: "ws://")
                guard let url = URL(string: "\(base)/v1/stream?ticket=\(ticket.ticket)") else { return }
                let socket = URLSession.shared.webSocketTask(with: url)
                task = socket
                socket.resume()
                backoff = 1
                while running {
                    _ = try await socket.receive()
                    onEvent()
                }
            } catch {
                guard running else { return }
                try? await Task.sleep(nanoseconds: backoff * 1_000_000_000)
                backoff = min(backoff * 2, 30)
            }
        }
    }
}
