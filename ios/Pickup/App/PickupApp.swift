import SwiftUI
import UIKit
import UserNotifications

@main
struct PickupApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .task { await model.start() }
                .onOpenURL { model.handle(url: $0) }
        }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        switch app.phase {
        case .loading:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity).background(Color.paper)
        case .onboarding:
            OnboardingView()
        case .main:
            MainTabs()
        }
    }
}

struct MainTabs: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("Calls", systemImage: "phone.fill") }
            ChatView()
                .tabItem { Label("Ask Pickup", systemImage: "sparkles") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}

/// Push notification plumbing: the APNs device token, and taps on notifications.
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        Task { @MainActor in AppModel.shared.observeLiveActivities() }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task { @MainActor in await AppModel.shared.didReceivePushToken(token) }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        Task { @MainActor in AppModel.shared.liveTick += 1 }
        return [.banner, .sound, .list]
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        let callId = response.notification.request.content.userInfo["call_id"] as? String
        await MainActor.run { AppModel.shared.openCallId = callId }
    }
}
