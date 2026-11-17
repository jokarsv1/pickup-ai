import SwiftUI

@MainActor
@Observable
final class SettingsModel {
    var assistant = Assistant()
    var options = AssistantOptions()
    var entitlement: Entitlement?
    var line: Line?
    var loaded = false
    var error: String?
    var saved: String?

    func load() async {
        do {
            assistant = try await API.shared.get("/v1/assistant")
            options = try await API.shared.get("/v1/assistant/options")
            entitlement = try? await API.shared.get("/v1/me/entitlement")
            line = try? await API.shared.get("/v1/lines/current")
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loaded = true
    }

    func update(_ patch: AssistantPatch, saved message: String? = nil) async {
        do {
            assistant = try await API.shared.patch("/v1/assistant", patch)
            saved = message
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func setRingSeconds(_ seconds: Int) async {
        guard let line else { return }
        if let updated: Line = try? await API.shared.patch("/v1/lines/\(line.id)", LinePatch(ringSeconds: seconds)) {
            self.line = updated
        }
    }

    func toggleLanguage(_ code: String) async {
        var languages = assistant.languages
        if let i = languages.firstIndex(of: code) {
            guard languages.count > 1 else { return }
            languages.remove(at: i)
        } else {
            guard languages.count < 3 else { error = "Pick up to three languages"; return }
            languages.append(code)
        }
        await update(AssistantPatch(languages: languages))
    }
}

struct SettingsView: View {
    @Environment(AppModel.self) private var app
    @State private var model = SettingsModel()
    @State private var confirmDelete = false
    @State private var confirmSignOut = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading) {
                        Text(app.user?.name ?? "Your name").font(.headline)
                        Text(Format.phone(app.user?.phone)).font(.subheadline).foregroundStyle(.secondary)
                    }
                    if let entitlement = model.entitlement, let plan = PlanText.short(entitlement) {
                        Label(plan, systemImage: "star.circle")
                    }
                }

                Section {
                    NavigationLink { InstructionsView(model: model) } label: {
                        VStack(alignment: .leading) {
                            Text("Instructions")
                            Text("How to handle deliveries, banks, sales calls and more").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    Picker("Voice", selection: Binding(get: { model.assistant.voice }, set: { voice in Task { await model.update(AssistantPatch(voice: voice)) } })) {
                        ForEach(model.options.voices) { Text($0.label).tag($0.id) }
                    }
                    NavigationLink { LanguagesView(model: model) } label: {
                        LabeledContent("Languages", value: model.assistant.languages.compactMap { model.options.languages[$0] }.joined(separator: ", "))
                    }
                } header: { Text("Your assistant") }

                Section {
                    Toggle("Connect urgent calls", isOn: Binding(get: { model.assistant.urgentPassthrough }, set: { on in Task { await model.update(AssistantPatch(urgentPassthrough: on)) } }))
                    Toggle("Record calls", isOn: Binding(get: { model.assistant.recordCalls }, set: { on in Task { await model.update(AssistantPatch(recordCalls: on)) } }))
                } header: { Text("During calls") } footer: {
                    Text("Your assistant puts genuine emergencies straight through to you. Recordings are kept for \(model.assistant.retentionDays) days.")
                }

                Section {
                    NavigationLink { ForwardingSettingsView() } label: {
                        LabeledContent("Call forwarding", value: model.line?.isVerified == true ? "Working" : "Not set up")
                    }
                } header: { Text("Call forwarding") }

                Section {
                    Link("Privacy policy", destination: URL(string: API.baseURL + "/legal/privacy")!)
                    Link("Terms of service", destination: URL(string: API.baseURL + "/legal/terms")!)
                }

                Section {
                    Button("Sign out") { confirmSignOut = true }
                    Button("Delete account", role: .destructive) { confirmDelete = true }
                } footer: {
                    Text("Pickup \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "")")
                }

                if let error = model.error {
                    Text(error).foregroundStyle(Color.danger)
                }
            }
            .navigationTitle("Settings")
            .task { await model.load() }
            .confirmationDialog("Sign out of Pickup?", isPresented: $confirmSignOut, titleVisibility: .visible) {
                Button("Sign out", role: .destructive) { Task { await app.signOut() } }
            }
            .confirmationDialog("Delete your account? Your calls, recordings and settings are deleted. Turn off call forwarding first (dial ##002#).", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete account", role: .destructive) {
                    Task {
                        try? await API.shared.delete("/v1/me")
                        await app.signOut()
                    }
                }
            }
        }
    }
}

struct LanguagesView: View {
    var model: SettingsModel

    var body: some View {
        List {
            ForEach(model.options.languages.map { ChipItem(id: $0.key, label: $0.value) }.sorted { $0.label < $1.label }) { item in
                Button { Task { await model.toggleLanguage(item.id) } } label: {
                    HStack {
                        Text(item.label).foregroundStyle(.primary)
                        Spacer()
                        if model.assistant.languages.contains(item.id) { Image(systemName: "checkmark").foregroundStyle(Color.ink) }
                    }
                }
            }
            if let error = model.error { Text(error).foregroundStyle(Color.danger) }
        }
        .navigationTitle("Languages")
    }
}

struct InstructionsView: View {
    var model: SettingsModel
    @State private var instructions = ""
    @State private var deliveryNote = ""

    var body: some View {
        Form {
            Section {
                ForEach(model.options.packs) { pack in
                    Toggle(isOn: Binding(
                        get: { model.assistant.packIds.contains(pack.id) },
                        set: { on in
                            var ids = model.assistant.packIds.filter { $0 != pack.id }
                            if on { ids.append(pack.id) }
                            Task { await model.update(AssistantPatch(packIds: ids)) }
                        }
                    )) {
                        VStack(alignment: .leading) {
                            Text(pack.title)
                            Text(pack.subtitle).font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }
            } header: { Text("Ready-made packs") } footer: {
                Text("Your assistant follows these on every call.")
            }
            Section {
                TextField("If it's my landlord, say I'll call after 6", text: $instructions, axis: .vertical).lineLimit(3...8)
            } header: { Text("In your words") }
            Section {
                TextField("Leave parcels with the guard at Gate 2", text: $deliveryNote, axis: .vertical)
            } header: { Text("Delivery note") }
            Section {
                Button("Save") {
                    Task { await model.update(AssistantPatch(instructions: instructions, deliveryNote: deliveryNote), saved: "Saved") }
                }
                if let saved = model.saved { Text(saved).foregroundStyle(Color.success) }
            }
        }
        .navigationTitle("Instructions")
        .onAppear {
            instructions = model.assistant.instructions
            deliveryNote = model.assistant.deliveryNote ?? ""
        }
    }
}

/// Shows the forwarding codes again, the ring time, and how to turn forwarding off.
struct ForwardingSettingsView: View {
    @State private var line: Line?
    @State private var copied: String?
    @State private var verifying = false
    @State private var message: String?
    @State private var loaded = false

    var body: some View {
        List {
            if let line {
                Section {
                    LabeledContent("Assistant number", value: line.assistantNumberDisplay)
                    LabeledContent("Status", value: line.isVerified ? "Working" : "Not confirmed yet")
                } footer: {
                    Text("Calls you decline or don't pick up go to this number, and your assistant answers.")
                }
                Section {
                    ForEach(line.activationCodes) { code in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(code.title).font(.headline)
                            Text(code.description).font(.footnote).foregroundStyle(.secondary)
                            HStack {
                                Text(code.code).font(.body.monospaced())
                                Spacer()
                                Button(copied == code.code ? "Copied" : "Copy") {
                                    UIPasteboard.general.string = code.code
                                    copied = code.code
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                } header: { Text("Codes to dial") } footer: {
                    Text("Copy a code, open the Phone app, paste it on the keypad (tap and hold above the keys) and press call.")
                }
                Section {
                    Button(verifying ? "Calling you…" : "Test it: call me now") {
                        Task {
                            verifying = true
                            do {
                                let _: Empty = try await API.shared.post("/v1/lines/\(line.id)/verify")
                                message = "We're calling you. Tap Decline: if forwarding works, your assistant picks it up."
                            } catch {
                                message = error.localizedDescription
                            }
                            verifying = false
                        }
                    }
                    .disabled(verifying)
                    if let message { Text(message).font(.footnote).foregroundStyle(.secondary) }
                }
                Section {
                    HStack {
                        Text(line.deactivationAllCode).font(.body.monospaced())
                        Spacer()
                        Button(copied == line.deactivationAllCode ? "Copied" : "Copy") {
                            UIPasteboard.general.string = line.deactivationAllCode
                            copied = line.deactivationAllCode
                        }
                        .buttonStyle(.bordered)
                    }
                } header: { Text("Turn forwarding off") } footer: {
                    Text("Dial this to stop all call forwarding, for example before you delete your account.")
                }
            } else if loaded {
                Text("No assistant number yet. We're setting up more numbers; check back soon.").foregroundStyle(.secondary)
            } else {
                ProgressView()
            }
        }
        .navigationTitle("Call forwarding")
        .task {
            line = try? await API.shared.get("/v1/lines/current")
            if line == nil { line = try? await API.shared.post("/v1/lines", LineBody()) }
            loaded = true
        }
    }
}
