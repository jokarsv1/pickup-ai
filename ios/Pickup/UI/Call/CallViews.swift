import SwiftUI

@MainActor
@Observable
final class CallModel {
    let callId: String
    var call: CallDetail?
    var error: String?
    var draft = ""
    var notice: String?
    var sending = false

    init(callId: String) { self.callId = callId }

    func load() async {
        do {
            call = try await API.shared.get("/v1/calls/\(callId)")
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func markRead() async {
        let _: Empty? = try? await API.shared.post("/v1/calls/\(callId)/read")
    }

    func rate(_ stars: Int) async {
        let _: Empty? = try? await API.shared.post("/v1/calls/\(callId)/feedback", FeedbackBody(rating: stars))
        call?.rating = stars
    }

    func setAction(_ action: CallAction, status: String) async {
        let _: CallAction? = try? await API.shared.post("/v1/calls/\(callId)/actions/\(action.id)", ActionStatusBody(status: status))
        await load()
    }

    func delete() async -> Bool {
        do {
            try await API.shared.delete("/v1/calls/\(callId)")
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }

    func say(_ text: String) async {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        sending = true
        defer { sending = false }
        do {
            let _: Empty = try await API.shared.post("/v1/calls/\(callId)/say", SayBody(text: text))
            draft = ""
            notice = "Sent to your assistant"
        } catch {
            notice = error.localizedDescription
        }
    }

    func join() async {
        do {
            let _: Empty = try await API.shared.post("/v1/calls/\(callId)/takeover")
            notice = "Your phone will ring in a few seconds. Answer it to talk to the caller."
        } catch {
            notice = error.localizedDescription
        }
    }

    func end() async {
        do {
            let _: Empty = try await API.shared.post("/v1/calls/\(callId)/end")
            notice = "Your assistant is wrapping up the call"
        } catch {
            notice = error.localizedDescription
        }
    }
}

struct CallDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var model: CallModel
    @State private var confirmDelete = false

    init(callId: String) { _model = State(initialValue: CallModel(callId: callId)) }

    var body: some View {
        ScrollView {
            if let call = model.call {
                VStack(alignment: .leading, spacing: 18) {
                    header(call)
                    if let summary = call.summary, !summary.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Summary").font(.caption).foregroundStyle(.secondary)
                            Text(summary).font(.body)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.card, in: RoundedRectangle(cornerRadius: 18))
                    }
                    actions(call)
                    if !call.transcript.isEmpty {
                        Text("CONVERSATION").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                        ForEach(call.transcript) { line in Bubble(speaker: line.speaker, text: line.text, ownerName: Format.firstName(app.user?.name)) }
                    }
                    if !call.isLive {
                        Text("HOW DID YOUR ASSISTANT DO?").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                        HStack(spacing: 14) {
                            ForEach(1...5, id: \.self) { star in
                                Button { Task { await model.rate(star) } } label: {
                                    Image(systemName: (call.rating ?? 0) >= star ? "star.fill" : "star").font(.title2).foregroundStyle(Color.saffron)
                                }
                                .accessibilityLabel("\(star) star\(star == 1 ? "" : "s")")
                            }
                        }
                    }
                }
                .padding()
            } else if let error = model.error {
                Text(error).foregroundStyle(.secondary).padding(.top, 80)
            } else {
                ProgressView().padding(.top, 80)
            }
        }
        .background(Color.paper)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(role: .destructive) { confirmDelete = true } label: { Image(systemName: "trash") }
                    .accessibilityLabel("Delete call")
            }
        }
        .confirmationDialog("Delete this call? Its summary, transcript and recording are removed.", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete", role: .destructive) { Task { if await model.delete() { dismiss() } } }
        }
        .task {
            await model.load()
            await model.markRead()
        }
        .onChange(of: app.liveTick) { Task { await model.load() } }
    }

    private func header(_ call: CallDetail) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 14) {
                CategoryAvatar(category: call.category, spam: call.isSpam, size: 56)
                VStack(alignment: .leading, spacing: 2) {
                    Text(call.title).font(.title2.bold())
                    Text([Format.phone(call.callerNumber), Format.dateTime(call.startedAt), Format.duration(call.durationSeconds)].filter { !$0.isEmpty }.joined(separator: " · "))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            HStack {
                let style = CategoryStyle.of(call.category, spam: call.isSpam)
                if call.category != nil || call.isSpam { Pill(text: call.categoryLabel ?? style.label, color: style.color) }
                if call.isSpam && call.category != "scam" { Pill(text: "Likely spam", color: .danger) }
                if call.urgency == "high" { Pill(text: "Urgent", color: .saffron) }
            }
        }
    }

    @ViewBuilder
    private func actions(_ call: CallDetail) -> some View {
        let open = call.actions.filter { $0.status == "open" }
        if !open.isEmpty || (call.callerNumber != nil && !call.isSpam) {
            Text("NEXT STEPS").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    if let number = call.callerNumber, !call.isSpam, !open.contains(where: { $0.type == "call_back" }), let url = URL(string: "tel:\(number)") {
                        Link(destination: url) { Label("Call back", systemImage: "phone.fill") }.buttonStyle(.bordered)
                    }
                    ForEach(open) { action in
                        if action.type == "call_back", let number = call.callerNumber, let url = URL(string: "tel:\(number)") {
                            Link(destination: url) { Label(action.title, systemImage: "phone.fill") }.buttonStyle(.bordered)
                        } else {
                            Button { Task { await model.setAction(action, status: "done") } } label: {
                                Label(action.title, systemImage: symbol(for: action.type))
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
            }
        }
    }

    private func symbol(for type: String) -> String {
        switch type {
        case "reminder": return "alarm"
        case "save_contact": return "person.badge.plus"
        case "block": return "nosign"
        default: return "checkmark.circle"
        }
    }
}

struct LiveCallView: View {
    @Environment(AppModel.self) private var app
    @State private var model: CallModel
    @FocusState private var typing: Bool

    init(callId: String) { _model = State(initialValue: CallModel(callId: callId)) }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        if let call = model.call {
                            HStack(spacing: 12) {
                                CategoryAvatar(category: call.category, spam: call.isSpam)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(call.reason?.isEmpty == false ? call.reason! : "Your assistant is talking to the caller").font(.headline)
                                    Text(Format.phone(call.callerNumber)).font(.footnote).foregroundStyle(.secondary)
                                }
                            }
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.card, in: RoundedRectangle(cornerRadius: 18))
                            ForEach(call.transcript) { line in Bubble(speaker: line.speaker, text: line.text, ownerName: Format.firstName(app.user?.name)).id(line.seq) }
                            if !call.isLive {
                                Label("The call has ended", systemImage: "phone.down.fill").foregroundStyle(.secondary)
                                NavigationLink(value: Route.call(call.id)) { Text("See the summary") }
                            }
                        } else {
                            ProgressView().frame(maxWidth: .infinity).padding(.top, 80)
                        }
                    }
                    .padding()
                }
                .onChange(of: model.call?.transcript.count ?? 0) {
                    if let last = model.call?.transcript.last { withAnimation { proxy.scrollTo(last.seq, anchor: .bottom) } }
                }
            }
            if let call = model.call, call.isLive { controls(call) }
        }
        .background(Color.paper)
        .navigationTitle(model.call?.title ?? "Live call")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await model.load()
            // Poll as a fallback to the live event stream while the call is on.
            while !Task.isCancelled, model.call?.isLive ?? true {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await model.load()
            }
        }
        .onChange(of: app.liveTick) { Task { await model.load() } }
    }

    private func controls(_ call: CallDetail) -> some View {
        VStack(spacing: 10) {
            if let notice = model.notice { Text(notice).font(.footnote).foregroundStyle(.secondary) }
            if !call.suggestedReplies.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(call.suggestedReplies, id: \.self) { reply in
                            Button(reply) { Task { await model.say(reply) } }.buttonStyle(.bordered).buttonBorderShape(.capsule)
                        }
                    }
                }
            }
            HStack {
                TextField("Tell your assistant what to say", text: $model.draft, axis: .vertical)
                    .focused($typing)
                    .padding(10)
                    .background(Color.card, in: RoundedRectangle(cornerRadius: 14))
                Button { Task { await model.say(model.draft) } } label: { Image(systemName: "paperplane.fill").font(.title3) }
                    .disabled(model.draft.trimmingCharacters(in: .whitespaces).isEmpty || model.sending)
                    .accessibilityLabel("Send")
            }
            HStack(spacing: 12) {
                Button { Task { await model.join() } } label: { Label("Join call", systemImage: "phone.fill").frame(maxWidth: .infinity, minHeight: 44) }
                    .buttonStyle(.borderedProminent)
                Button { Task { await model.end() } } label: { Label("End", systemImage: "phone.down.fill").frame(maxWidth: .infinity, minHeight: 44) }
                    .buttonStyle(.bordered)
            }
        }
        .padding()
        .background(.bar)
    }
}
