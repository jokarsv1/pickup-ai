import SwiftUI

@MainActor
@Observable
final class OnboardingModel {
    enum Step: Int, CaseIterable { case welcome, phone, code, profile, notifications, forwarding, verify, done }
    enum VerifyState { case idle, calling, success, failed }

    var step: Step = .welcome
    var config: PublicConfig?
    var phoneInput = ""
    var phoneE164: String?
    var code = ""
    var name = ""
    var languages: [String] = ["en-IN", "hi-IN"]
    var voice = "ritu"
    var voices: [VoiceOption] = []
    var line: Line?
    var busy = false
    var error: String?
    var waitingForNumber = false
    var verify: VerifyState = .idle
    var copied: String?

    static let languageChoices: [(String, String)] = [
        ("en-IN", "English"), ("hi-IN", "Hindi"), ("ta-IN", "Tamil"), ("te-IN", "Telugu"),
        ("kn-IN", "Kannada"), ("ml-IN", "Malayalam"), ("mr-IN", "Marathi"), ("bn-IN", "Bengali"), ("gu-IN", "Gujarati"),
    ]

    var betaOnly: Bool {
        guard let modes = config?.authModes else { return false }
        return modes.contains("beta") && !modes.contains("dev")
    }

    func go(_ step: Step) {
        error = nil
        self.step = step
    }

    /// Picks up where a signed-in user left off.
    func resume() async {
        config = try? await API.shared.get("/v1/config")
        guard await API.shared.hasSession else { return }
        guard let me: User = try? await API.shared.get("/v1/me") else { return }
        name = me.name ?? ""
        phoneE164 = me.phone
        if name.isEmpty { step = .profile; return }
        line = try? await API.shared.get("/v1/lines/current")
        if let line, line.isVerified { step = .done } else if line != nil { step = .forwarding } else { step = .notifications }
    }

    func submitPhone() async {
        guard let e164 = Format.indianMobile(phoneInput) else {
            error = "Enter a 10-digit Indian mobile number"
            return
        }
        busy = true
        defer { busy = false }
        if config == nil { config = try? await API.shared.get("/v1/config") }
        let modes = config?.authModes ?? []
        guard modes.contains("dev") || modes.contains("beta") else {
            error = modes.isEmpty ? "Can't reach Pickup. Check your internet connection." : "SMS sign-in isn't available on iPhone yet. Ask for a beta code."
            return
        }
        phoneE164 = e164
        go(.code)
    }

    func submitCode(app: AppModel) async {
        guard let phoneE164, code.count == 6 else { return }
        busy = true
        defer { busy = false }
        do {
            let tokens: Tokens = try await API.shared.post("/v1/auth/dev", DevLogin(phone: phoneE164, code: code), auth: false)
            await app.signedIn(tokens)
            if tokens.user.onboardingCompleted {
                app.finishOnboarding()
                return
            }
            name = tokens.user.name ?? ""
            if name.isEmpty {
                await loadVoices()
                go(.profile)
            } else {
                await resume()
            }
        } catch {
            code = ""
            self.error = error.localizedDescription
        }
    }

    func loadVoices() async {
        if let options: AssistantOptions = try? await API.shared.get("/v1/assistant/options") {
            voices = options.voices
        }
    }

    func toggleLanguage(_ code: String) {
        if let i = languages.firstIndex(of: code) {
            if languages.count > 1 { languages.remove(at: i) }
        } else if languages.count < 3 {
            languages.append(code)
        }
    }

    func saveProfile() async {
        busy = true
        defer { busy = false }
        do {
            let _: User = try await API.shared.patch("/v1/me", MePatch(name: name.trimmingCharacters(in: .whitespaces), language: languages.first))
            let _: Assistant = try await API.shared.patch("/v1/assistant", AssistantPatch(voice: voice, languages: languages))
            go(.notifications)
        } catch {
            self.error = error.localizedDescription
        }
    }

    func notificationsDone(app: AppModel, allow: Bool) async {
        if allow { _ = await app.askForNotifications() }
        await createLine()
    }

    func createLine() async {
        busy = true
        defer { busy = false }
        do {
            if let current: Line = try? await API.shared.get("/v1/lines/current") {
                line = current
            } else {
                line = try await API.shared.post("/v1/lines", LineBody())
            }
            waitingForNumber = false
            go(line?.isVerified == true ? .done : .forwarding)
        } catch let error as APIError {
            waitingForNumber = error.status == 503
            step = .forwarding
            self.error = error.message
        } catch {
            self.error = error.localizedDescription
        }
    }

    func copy(_ code: String) {
        UIPasteboard.general.string = code
        copied = code
    }

    func startVerify() async {
        guard let line else { return }
        verify = .calling
        error = nil
        do {
            let _: Empty = try await API.shared.post("/v1/lines/\(line.id)/verify")
        } catch {
            verify = .failed
            self.error = error.localizedDescription
            return
        }
        for _ in 0..<40 {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            if let current: Line = try? await API.shared.get("/v1/lines/current"), current.isVerified {
                self.line = current
                verify = .success
                return
            }
        }
        verify = .failed
        error = "We didn't see the call come back. Check that you dialled all three codes, then try again."
    }

    func finish(app: AppModel) async {
        let _: User? = try? await API.shared.patch("/v1/me", MePatch(onboardingCompleted: true))
        app.finishOnboarding()
    }
}
