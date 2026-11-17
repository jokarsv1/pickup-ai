import SwiftUI

struct OnboardingView: View {
    @Environment(AppModel.self) private var app
    @State private var model = OnboardingModel()

    var body: some View {
        Group {
            switch model.step {
            case .welcome: WelcomeStep(model: model)
            case .phone: PhoneStep(model: model)
            case .code: CodeStep(model: model)
            case .profile: ProfileStep(model: model)
            case .notifications: NotificationsStep(model: model)
            case .forwarding: ForwardingStep(model: model)
            case .verify: VerifyStep(model: model)
            case .done: DoneStep(model: model)
            }
        }
        .background(Color.paper.ignoresSafeArea())
        .animation(.default, value: model.step)
        .task { await model.resume() }
    }
}

/// Shared layout: progress, title, body text, scrolling content, and buttons pinned at the bottom.
struct StepLayout<Content: View, Footer: View>: View {
    var progress: Int?
    var title: String
    var subtitle: String?
    var error: String?
    @ViewBuilder var content: Content
    @ViewBuilder var footer: Footer

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let progress {
                        HStack(spacing: 6) {
                            ForEach(0..<6, id: \.self) { i in
                                Capsule().fill(i <= progress ? Color.ink : Color.secondary.opacity(0.25)).frame(width: i == progress ? 28 : 16, height: 5)
                            }
                        }
                        .padding(.top, 8)
                    }
                    Text(title).font(.largeTitle.bold()).fixedSize(horizontal: false, vertical: true)
                    if let subtitle { Text(subtitle).font(.body).foregroundStyle(.secondary) }
                    if let error {
                        Label(error, systemImage: "exclamationmark.circle.fill")
                            .font(.callout)
                            .foregroundStyle(Color.danger)
                            .accessibilityIdentifier("onboarding.error")
                    }
                    content
                }
                .padding(24)
            }
            .scrollDismissesKeyboard(.interactively) // drag down to reach choices under the keyboard
            VStack(spacing: 8) { footer }
                .padding(.horizontal, 24)
                .padding(.bottom, 16)
        }
    }
}

private struct WelcomeStep: View {
    var model: OnboardingModel

    var body: some View {
        StepLayout(progress: nil, title: "Let AI take your calls.", subtitle: "Pickup answers the calls you can't or don't want to take, finds out who's calling and why, and tells you in seconds.") {
            VStack(alignment: .leading, spacing: 20) {
                Benefit(symbol: "shield.fill", title: "Spam and scams never reach you", text: "Loan offers, fake KYC and 'parcel seized' calls end with your assistant.")
                Benefit(symbol: "bolt.fill", title: "Live transcript, one-tap replies", text: "Read the call as it happens. Tell your assistant what to say, or join in.")
                Benefit(symbol: "character.bubble.fill", title: "Speaks like your callers", text: "Hindi, English, Hinglish and more Indian languages.")
            }
            .padding(.top, 16)
        } footer: {
            PrimaryButton(title: "Get started") { model.go(.phone) }
            Text("Free for 7 days. No card needed.").font(.footnote).foregroundStyle(.secondary)
        }
    }
}

struct Benefit: View {
    var symbol: String
    var title: String
    var text: String

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: symbol)
                .foregroundStyle(Color.ink)
                .frame(width: 44, height: 44)
                .background(Color.ink.opacity(0.12), in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.headline)
                Text(text).font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }
}

private struct PhoneStep: View {
    @Bindable var model: OnboardingModel

    var body: some View {
        StepLayout(progress: 0, title: "What's your mobile number?", subtitle: "Use the number on this iPhone. Your assistant answers calls to it.", error: model.error) {
            TextField("98765 43210", text: $model.phoneInput)
                .keyboardType(.phonePad)
                .textContentType(.telephoneNumber)
                .font(.title2)
                .padding()
                .background(Color.card, in: RoundedRectangle(cornerRadius: 14))
                .accessibilityIdentifier("onboarding.phone")
        } footer: {
            PrimaryButton(title: "Send code", loading: model.busy, enabled: model.phoneInput.filter(\.isNumber).count >= 10) {
                Task { await model.submitPhone() }
            }
            Button("Back") { model.go(.welcome) }
        }
    }
}

private struct CodeStep: View {
    @Environment(AppModel.self) private var app
    @Bindable var model: OnboardingModel

    var body: some View {
        StepLayout(
            progress: 0,
            title: model.betaOnly ? "Enter your beta code" : "Enter the code",
            subtitle: model.betaOnly ? "Pickup is in private beta. Enter the code you were given for \(Format.phone(model.phoneE164))." : "Enter the 6-digit code for \(Format.phone(model.phoneE164)).",
            error: model.error
        ) {
            TextField("······", text: $model.code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .font(.title.monospacedDigit())
                .padding()
                .background(Color.card, in: RoundedRectangle(cornerRadius: 14))
                .accessibilityIdentifier("onboarding.code")
                .onChange(of: model.code) {
                    let digits = String(model.code.filter(\.isNumber).prefix(6))
                    if digits != model.code { model.code = digits }
                    if digits.count == 6 { Task { await model.submitCode(app: app) } }
                }
            if let hint = model.config?.devCodeHint { Text("Development code: \(hint)").font(.footnote).foregroundStyle(.secondary) }
        } footer: {
            PrimaryButton(title: "Verify", loading: model.busy, enabled: model.code.count == 6) {
                Task { await model.submitCode(app: app) }
            }
            Button("Change number") { model.go(.phone) }
        }
    }
}

private struct ProfileStep: View {
    @Bindable var model: OnboardingModel

    var body: some View {
        StepLayout(progress: 1, title: "Make it yours", subtitle: "Your assistant introduces itself as yours, in your callers' language.", error: model.error) {
            TextField("Your name", text: $model.name)
                .textContentType(.name)
                .submitLabel(.done)
                .font(.title3)
                .padding()
                .background(Color.card, in: RoundedRectangle(cornerRadius: 14))
                .accessibilityIdentifier("onboarding.name")
            Text("Languages your callers speak").font(.headline).padding(.top, 8)
            Text("Pick up to three. Your assistant mixes them naturally, like Hinglish.").font(.footnote).foregroundStyle(.secondary)
            FlowChips(items: OnboardingModel.languageChoices.map { ChipItem(id: $0.0, label: $0.1) }, selected: Set(model.languages)) { model.toggleLanguage($0) }
            if !model.voices.isEmpty {
                Text("Voice").font(.headline).padding(.top, 8)
                FlowChips(items: model.voices.map { ChipItem(id: $0.id, label: $0.label) }, selected: [model.voice]) { model.voice = $0 }
            }
        } footer: {
            PrimaryButton(title: "Continue", loading: model.busy, enabled: !model.name.trimmingCharacters(in: .whitespaces).isEmpty) {
                Task { await model.saveProfile() }
            }
        }
        .task { if model.voices.isEmpty { await model.loadVoices() } }
    }
}

struct ChipItem: Identifiable, Hashable {
    var id: String
    var label: String
}

/// Wrapping row of selectable chips.
struct FlowChips: View {
    var items: [ChipItem]
    var selected: Set<String>
    var onTap: (String) -> Void

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(items) { item in
                let on = selected.contains(item.id)
                Button { onTap(item.id) } label: {
                    Text(item.label)
                        .font(.subheadline.weight(.medium))
                        .lineLimit(1)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(on ? Color.ink.opacity(0.16) : Color.card, in: Capsule())
                        .overlay(Capsule().stroke(on ? Color.ink : Color.secondary.opacity(0.3)))
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }
}

private struct NotificationsStep: View {
    @Environment(AppModel.self) private var app
    var model: OnboardingModel

    var body: some View {
        StepLayout(progress: 2, title: "Know who's calling, live", subtitle: "Pickup tells you who's on the line and why while your assistant talks to them, and sends a summary when they hang up.", error: model.error) {
            VStack(alignment: .leading, spacing: 20) {
                Benefit(symbol: "bell.badge.fill", title: "Live alerts", text: "\"Live: Ramesh · Blue Dart. Parcel at the gate, needs OTP.\"")
                Benefit(symbol: "text.bubble.fill", title: "Summaries", text: "Who called, why, and what to do next, seconds after the call.")
            }
            .padding(.top, 8)
        } footer: {
            PrimaryButton(title: "Allow notifications", loading: model.busy) { Task { await model.notificationsDone(app: app, allow: true) } }
            Button("Not now") { Task { await model.notificationsDone(app: app, allow: false) } }
        }
    }
}

private struct ForwardingStep: View {
    var model: OnboardingModel

    var body: some View {
        StepLayout(
            progress: 3,
            title: "Send missed calls to your assistant",
            subtitle: "Your carrier forwards calls you decline or don't pick up. Copy each code, open the Phone app, paste it on the keypad and press call. Do it once for each.",
            error: model.error
        ) {
            if let line = model.line {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Your assistant's number").font(.caption).foregroundStyle(.secondary)
                    Text(line.assistantNumberDisplay).font(.title2.bold().monospacedDigit())
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color.ink.opacity(0.12), in: RoundedRectangle(cornerRadius: 16))
                ForEach(Array(line.activationCodes.enumerated()), id: \.element.key) { index, code in
                    CodeCard(number: index + 1, code: code, copied: model.copied == code.code) { model.copy(code.code) }
                }
                if let note = line.carrierNote { Text(note).font(.footnote).foregroundStyle(.secondary) }
                Label("Tip: in Settings › Apps › Phone, turn on Silence Unknown Callers. Calls from numbers not in your contacts then go straight to your assistant, while contacts still ring.", systemImage: "lightbulb")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            } else if model.waitingForNumber {
                Text("We're setting up more assistant numbers. You can explore Pickup now and finish this from the Calls tab later.")
                    .foregroundStyle(.secondary)
            } else {
                ProgressView()
            }
        } footer: {
            if model.line != nil {
                PrimaryButton(title: "I've dialled all three") { model.go(.verify) }
            } else {
                PrimaryButton(title: "Try again", loading: model.busy) { Task { await model.createLine() } }
                if model.waitingForNumber { Button("Skip for now") { model.go(.done) } }
            }
        }
    }
}

private struct CodeCard: View {
    var number: Int
    var code: ForwardingCode
    var copied: Bool
    var onCopy: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Text("\(number)").font(.headline).foregroundStyle(.white).frame(width: 28, height: 28).background(Color.ink, in: Circle())
                Text(code.title).font(.headline)
            }
            Text(code.help).font(.footnote).foregroundStyle(.secondary)
            HStack {
                Text(code.code).font(.body.monospaced()).textSelection(.enabled)
                Spacer()
                Button(copied ? "Copied" : "Copy", action: onCopy)
                    .buttonStyle(.bordered)
                    .buttonBorderShape(.capsule)
            }
        }
        .padding()
        .background(Color.card, in: RoundedRectangle(cornerRadius: 16))
    }
}

private struct VerifyStep: View {
    var model: OnboardingModel

    var body: some View {
        StepLayout(progress: 4, title: "Let's test it", subtitle: "We'll call you from your assistant's number. When your iPhone rings, tap Decline. If forwarding works, the call comes straight back to your assistant.", error: model.error) {
            switch model.verify {
            case .idle: EmptyView()
            case .calling: Label("Calling you now. Tap Decline when it rings.", systemImage: "phone.arrow.down.left").foregroundStyle(Color.ink)
            case .success: Label("It works. Your assistant will answer calls you decline or miss.", systemImage: "checkmark.seal.fill").foregroundStyle(Color.success)
            case .failed: EmptyView()
            }
        } footer: {
            switch model.verify {
            case .idle: PrimaryButton(title: "Call me now") { Task { await model.startVerify() } }
            case .calling: PrimaryButton(title: "Waiting for the call…", loading: true) {}
            case .success: PrimaryButton(title: "Continue") { model.go(.done) }
            case .failed:
                PrimaryButton(title: "Try again") { Task { await model.startVerify() } }
                Button("Dial the codes again") { model.go(.forwarding) }
            }
            if model.verify != .success { Button("Skip for now") { model.go(.done) } }
        }
    }
}

private struct DoneStep: View {
    @Environment(AppModel.self) private var app
    var model: OnboardingModel

    var body: some View {
        let ready = model.line?.isVerified == true
        StepLayout(progress: nil, title: ready ? "You're all set" : "Almost there", subtitle: ready ? "Here's how to get the most out of Pickup." : "Calls ring you normally until call forwarding is set up. Finish it any time from the Calls tab.") {
            VStack(alignment: .leading, spacing: 20) {
                Benefit(symbol: "phone.down.fill", title: "Decline to hand over", text: "Tap Decline on any call and your assistant picks it up.")
                Benefit(symbol: "bolt.fill", title: "Watch calls live", text: "Open the alert to read the call, reply in one tap, or join in.")
                Benefit(symbol: "shield.fill", title: "Teach it once", text: "Settings › Instructions: tell it how to handle deliveries, banks, sales calls and more.")
            }
            .padding(.top, 8)
        } footer: {
            PrimaryButton(title: "Go to Pickup") { Task { await model.finish(app: app) } }
        }
    }
}
