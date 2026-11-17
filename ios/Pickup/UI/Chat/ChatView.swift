import SwiftUI

@MainActor
@Observable
final class ChatModel {
    var messages: [ChatMessage] = []
    var draft = ""
    var sending = false
    var error: String?

    func load() async {
        do {
            messages = try await API.shared.get("/v1/assistant/chat")
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        sending = true
        draft = ""
        messages.append(ChatMessage(id: -(messages.count + 1), role: "user", text: text))
        defer { sending = false }
        do {
            let reply: ChatReply = try await API.shared.post("/v1/assistant/chat", ChatBody(text: text))
            messages = reply.messages.isEmpty ? messages + [ChatMessage(id: -(messages.count + 1), role: "assistant", text: reply.reply)] : reply.messages
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct ChatView: View {
    @State private var model = ChatModel()

    private let suggestions = [
        "Who called today?",
        "Call the plumber at 5 and ask when he's coming",
        "If my bank calls, ask them to email me",
    ]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            if model.messages.isEmpty {
                                VStack(alignment: .leading, spacing: 10) {
                                    Text("Ask your assistant to call someone, remind you, or change how it handles calls.").foregroundStyle(.secondary)
                                    ForEach(suggestions, id: \.self) { text in
                                        Button(text) { model.draft = text }.buttonStyle(.bordered).buttonBorderShape(.capsule)
                                    }
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            ForEach(model.messages) { message in
                                ChatBubble(message: message).id(message.id)
                            }
                            if model.sending { ProgressView().frame(maxWidth: .infinity, alignment: .leading) }
                            if let error = model.error { Text(error).font(.footnote).foregroundStyle(Color.danger) }
                        }
                        .padding()
                    }
                    .onChange(of: model.messages.count) {
                        if let last = model.messages.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
                    }
                }
                HStack(alignment: .bottom) {
                    TextField("Ask Pickup to call, remind or change settings", text: $model.draft, axis: .vertical)
                        .lineLimit(1...4)
                        .padding(10)
                        .background(Color.card, in: RoundedRectangle(cornerRadius: 16))
                        .accessibilityIdentifier("chat.input")
                    Button { Task { await model.send() } } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }
                        .disabled(model.draft.trimmingCharacters(in: .whitespaces).isEmpty || model.sending)
                        .accessibilityLabel("Send")
                }
                .padding()
                .background(.bar)
            }
            .background(Color.paper)
            .navigationTitle("Ask Pickup")
            .task { await model.load() }
        }
    }
}

private struct ChatBubble: View {
    var message: ChatMessage

    var body: some View {
        let mine = message.role == "user"
        Text(message.text)
            .padding(12)
            .foregroundStyle(mine ? Color.white : Color.primary)
            .background(mine ? Color.ink : Color.secondary.opacity(0.15), in: RoundedRectangle(cornerRadius: 18))
            .frame(maxWidth: .infinity, alignment: mine ? .trailing : .leading)
            .padding(mine ? .leading : .trailing, 48)
    }
}
