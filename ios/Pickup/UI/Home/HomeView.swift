import SwiftUI

@MainActor
@Observable
final class HomeModel {
    var calls: [CallSummary] = []
    var live: [CallSummary] = []
    var stats: Stats?
    var entitlement: Entitlement?
    var line: Line?
    var lineLoaded = false
    var nextCursor: String?
    var category: String?
    var query = ""
    var loaded = false
    var error: String?

    struct Filter: Identifiable { var key: String?; var label: String; var id: String { label } }
    struct DaySection: Identifiable { var id: String; var calls: [CallSummary] }

    static let filters: [Filter] = [
        Filter(key: nil, label: "All"), Filter(key: "delivery", label: "Deliveries"), Filter(key: "bank_finance", label: "Banks"),
        Filter(key: "personal", label: "Personal"), Filter(key: "recruiter", label: "Jobs"), Filter(key: "scam", label: "Scams"),
    ]

    func load() async {
        let listPath = path()
        do {
            async let page: CallPage = API.shared.get(listPath)
            async let live: [CallSummary] = API.shared.get("/v1/calls/live")
            async let stats: Stats? = try? API.shared.get("/v1/me/stats")
            async let entitlement: Entitlement? = try? API.shared.get("/v1/me/entitlement")
            async let line: Line? = try? API.shared.get("/v1/lines/current")
            let result = try await page
            calls = result.items
            nextCursor = result.nextCursor
            self.live = try await live
            self.stats = await stats
            self.entitlement = await entitlement
            self.line = await line
            lineLoaded = true
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loaded = true
    }

    func loadMore() async {
        guard let cursor = nextCursor else { return }
        nextCursor = nil
        if let page: CallPage = try? await API.shared.get(path(cursor: cursor)) {
            calls += page.items
            nextCursor = page.nextCursor
        }
    }

    private func path(cursor: String? = nil) -> String {
        var items: [URLQueryItem] = []
        if let category { items.append(URLQueryItem(name: "category", value: category)) }
        let q = query.trimmingCharacters(in: .whitespaces)
        if !q.isEmpty { items.append(URLQueryItem(name: "q", value: q)) }
        if let cursor { items.append(URLQueryItem(name: "cursor", value: cursor)) }
        var components = URLComponents()
        components.queryItems = items.isEmpty ? nil : items
        return "/v1/calls" + (components.percentEncodedQuery.map { "?" + $0 } ?? "")
    }

    /// Calls grouped under "Today", "Yesterday", or a date, newest first.
    var sections: [DaySection] {
        var result: [DaySection] = []
        for call in calls {
            let day = Format.dayLabel(call.startedAt)
            if let last = result.last, last.id == day {
                result[result.count - 1].calls.append(call)
            } else {
                result.append(DaySection(id: day, calls: [call]))
            }
        }
        return result
    }
}

struct HomeView: View {
    @Environment(AppModel.self) private var app
    @State private var model = HomeModel()
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section {
                    StatusCard(model: model)
                    ForEach(model.live) { call in
                        NavigationLink(value: Route.live(call.id)) { LiveBanner(call: call) }
                            .listRowBackground(Color.liveTint)
                    }
                    if let stats = model.stats, stats.callsHandled > 0 { StatsRow(stats: stats) }
                    FilterChips(model: model)
                }
                .listRowSeparator(.hidden)

                if let error = model.error {
                    Label(error, systemImage: "wifi.exclamationmark").foregroundStyle(.secondary)
                }
                if model.loaded && model.calls.isEmpty && model.error == nil {
                    EmptyCalls(line: model.line)
                }
                ForEach(model.sections) { section in
                    Section(section.id) {
                        ForEach(section.calls) { call in
                            NavigationLink(value: Route.call(call.id)) { CallRow(call: call) }
                                .onAppear { if call.id == model.calls.last?.id { Task { await model.loadMore() } } }
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            .background(Color.paper)
            .navigationTitle("\(Format.greeting(hour: Calendar.current.component(.hour, from: Date()))), \(Format.firstName(app.user?.name))")
            .navigationBarTitleDisplayMode(.large)
            .searchable(text: $model.query, prompt: "Search calls")
            .onSubmit(of: .search) { Task { await model.load() } }
            .refreshable { await model.load() }
            .navigationDestination(for: Route.self) { route in
                Group {
                    switch route {
                    case .call(let id): CallDetailView(callId: id)
                    case .live(let id): LiveCallView(callId: id)
                    case .setup: ForwardingSettingsView()
                    }
                }
                .toolbarRole(.editor) // a plain back arrow, not "Good evening, Asha"
            }
        }
        .task { await model.load() }
        .onChange(of: app.liveTick) { Task { await model.load() } }
        .onChange(of: model.category) { Task { await model.load() } }
        .onChange(of: app.openCallId) {
            if let id = app.openCallId {
                path.append(Route.call(id))
                app.openCallId = nil
            }
        }
        .onChange(of: app.openLiveCallId) {
            if let id = app.openLiveCallId {
                path.append(Route.live(id))
                app.openLiveCallId = nil
            }
        }
    }
}

enum Route: Hashable {
    case call(String)
    case live(String)
    case setup
}

private struct StatusCard: View {
    var model: HomeModel

    var body: some View {
        let verified = model.line?.isVerified == true
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Circle().fill(verified ? Color.success : Color.saffron).frame(width: 10, height: 10)
                Text(verified ? "Your assistant is on" : "Finish setting up").font(.headline)
            }
            Text(verified ? "Decline a call, or let it ring, and your assistant answers. Saved contacts still reach you." : "Calls ring you normally until call forwarding is set up.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if !verified && model.lineLoaded {
                NavigationLink(value: Route.setup) { Text("Set up call forwarding").font(.subheadline.weight(.semibold)) }
            }
            if let entitlement = model.entitlement, let text = PlanText.short(entitlement) {
                Text(text).font(.footnote).foregroundStyle(Color.ink)
            }
        }
        .padding(.vertical, 6)
    }
}

enum PlanText {
    static func short(_ e: Entitlement) -> String? {
        switch e.level {
        case "trial":
            guard let end = Format.date(e.trialEndsAt) else { return "Pro trial" }
            let days = max(0, Calendar.current.dateComponents([.day], from: Date(), to: end).day ?? 0)
            return "Pro trial: \(days) day\(days == 1 ? "" : "s") left"
        case "pro": return "Pickup Pro"
        case "free": return e.callsLeftThisMonth.map { "Free plan: \($0) calls left this month" }
        default: return "Free calls used up: your assistant takes short messages. Your calls stay free."
        }
    }
}

private struct LiveBanner: View {
    var call: CallSummary

    var body: some View {
        HStack(spacing: 12) {
            Circle().fill(Color.saffron).frame(width: 12, height: 12)
            VStack(alignment: .leading, spacing: 2) {
                Text("Live: \(Format.callTitle(call.title, number: call.callerNumber))").font(.headline)
                if let reason = call.reason, !reason.isEmpty { Text(reason).font(.subheadline).foregroundStyle(.secondary) }
            }
            Spacer()
            Text("Listen").font(.subheadline.weight(.semibold)).foregroundStyle(Color.ink)
        }
        .padding(.vertical, 6)
        .accessibilityElement(children: .combine)
    }
}

private struct StatsRow: View {
    var stats: Stats

    var body: some View {
        HStack {
            Stat(value: "\(stats.callsHandled)", label: "calls handled")
            Stat(value: "\(stats.spamBlocked)", label: "spam stopped")
            Stat(value: "\(stats.minutesSaved) min", label: "of your time saved")
        }
    }

    private struct Stat: View {
        var value: String
        var label: String
        var body: some View {
            VStack(alignment: .leading, spacing: 2) {
                Text(value).font(.title2.bold())
                Text(label).font(.caption).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct FilterChips: View {
    var model: HomeModel

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(HomeModel.filters) { filter in
                    let on = model.category == filter.key
                    Button(filter.label) { model.category = filter.key }
                        .font(.subheadline.weight(.medium))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 7)
                        .background(on ? Color.ink.opacity(0.16) : Color.card, in: Capsule())
                        .overlay(Capsule().stroke(on ? Color.clear : Color.secondary.opacity(0.3)))
                        .buttonStyle(.plain)
                }
            }
        }
    }
}

struct CallRow: View {
    var call: CallSummary

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            CategoryAvatar(category: call.category, spam: call.isSpam)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(Format.callTitle(call.title, number: call.callerNumber)).font(.headline).lineLimit(1)
                    if call.notReached { Pill(text: "Missed", color: .saffron) }
                    if call.callerLabel?.hasPrefix("Verified") == true { Pill(text: "Verified", color: .success) }
                    if call.isSpam { Pill(text: "Spam", color: .danger) }
                    if call.urgency == "high" { Pill(text: "Urgent", color: .saffron) }
                }
                Text(call.summary ?? call.reason ?? "").font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
            }
            Spacer(minLength: 4)
            VStack(alignment: .trailing, spacing: 6) {
                Text(Format.clock(call.startedAt)).font(.caption).foregroundStyle(.secondary)
                if call.unread { Circle().fill(Color.ink).frame(width: 8, height: 8).accessibilityLabel("Unread") }
            }
        }
        .padding(.vertical, 4)
    }
}

private struct EmptyCalls: View {
    var line: Line?

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "phone.bubble.fill").font(.largeTitle).foregroundStyle(Color.ink)
            Text("No calls yet").font(.headline)
            Text("When someone calls and you don't pick up, your assistant answers and the summary shows up here.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            if let line {
                Link("Call my assistant to try it", destination: URL(string: "tel:\(line.assistantNumber)")!)
                    .buttonStyle(.bordered)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }
}
