import Foundation

struct APIError: LocalizedError {
    var status: Int
    var message: String
    var errorDescription: String? { message }
}

/// Talks to the Pickup backend. Access tokens last an hour; on a 401 the client swaps its
/// refresh token for a new pair once and retries.
actor API {
    static let shared = API()

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder
    private var refreshing: Task<Bool, Never>?
    /// The session tokens, kept in memory too so a Keychain that refuses writes (an unsigned
    /// simulator build, a locked device right after boot) never loses a fresh sign-in.
    private var accessToken: String?
    private var refreshToken: String?

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        session = URLSession(configuration: config)
        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    /// The server: the build setting PICKUP_API_BASE_URL, overridable in debug builds (UI tests).
    static var baseURL: String {
        #if DEBUG
        if let override = ProcessInfo.processInfo.environment["PICKUP_API_BASE_URL"], !override.isEmpty {
            return override
        }
        #endif
        return (Bundle.main.object(forInfoDictionaryKey: "PickupAPIBaseURL") as? String) ?? "https://pickup-ai-i6v0t.fly.dev"
    }

    var hasSession: Bool { currentRefreshToken != nil }

    var currentRefreshToken: String? {
        if refreshToken == nil { refreshToken = Keychain.get("refresh") }
        return refreshToken
    }

    private var currentAccessToken: String? {
        if accessToken == nil { accessToken = Keychain.get("access") }
        return accessToken
    }

    func saveTokens(_ tokens: Tokens) {
        accessToken = tokens.accessToken
        refreshToken = tokens.refreshToken
        Keychain.set("access", tokens.accessToken)
        Keychain.set("refresh", tokens.refreshToken)
    }

    func signOutLocally() {
        accessToken = nil
        refreshToken = nil
        Keychain.clear()
    }

    // MARK: Requests

    func get<T: Decodable>(_ path: String) async throws -> T {
        try await send("GET", path, body: nil)
    }

    func post<T: Decodable, B: Encodable>(_ path: String, _ body: B, auth: Bool = true) async throws -> T {
        try await send("POST", path, body: try encoder.encode(body), auth: auth)
    }

    func post<T: Decodable>(_ path: String) async throws -> T {
        try await send("POST", path, body: nil)
    }

    func patch<T: Decodable, B: Encodable>(_ path: String, _ body: B) async throws -> T {
        try await send("PATCH", path, body: try encoder.encode(body))
    }

    func delete(_ path: String) async throws {
        let _: Empty = try await send("DELETE", path, body: nil)
    }

    private func send<T: Decodable>(_ method: String, _ path: String, body: Data?, auth: Bool = true, retry: Bool = true) async throws -> T {
        guard let url = URL(string: API.baseURL + path) else { throw APIError(status: 0, message: "Bad address") }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if auth, let token = currentAccessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError(status: 0, message: "Can't reach Pickup. Check your internet connection.")
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if status == 401, auth, retry, await refreshTokens() {
            return try await send(method, path, body: body, auth: auth, retry: false)
        }
        guard (200..<300).contains(status) else { throw APIError(status: status, message: Self.message(from: data, status: status)) }
        if data.isEmpty || status == 204, let empty = Empty() as? T {
            return empty
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError(status: status, message: "Unexpected response from the server")
        }
    }

    private func refreshTokens() async -> Bool {
        if let refreshing { return await refreshing.value }
        let task = Task<Bool, Never> {
            guard let refresh = self.currentRefreshToken else { return false }
            do {
                let body = try self.encoder.encode(RefreshBody(refreshToken: refresh))
                let tokens: Tokens = try await self.send("POST", "/v1/auth/refresh", body: body, auth: false, retry: false)
                self.saveTokens(tokens)
                return true
            } catch {
                return false
            }
        }
        refreshing = task
        let ok = await task.value
        refreshing = nil
        return ok
    }

    private static func message(from data: Data, status: Int) -> String {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let detail = json["detail"] as? String { return detail }
            if let details = json["detail"] as? [[String: Any]], let first = details.first?["msg"] as? String { return first }
        }
        switch status {
        case 429: return "Too many attempts. Try again in a few minutes."
        case 500...: return "Pickup's server had a problem. Try again in a moment."
        default: return "Something went wrong (\(status))"
        }
    }
}
