package ai.pickup.app.data

import ai.pickup.app.BuildConfig
import android.os.Build
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.net.URLEncoder

/** One place for every backend call the screens make. */
class Repository(val api: ApiClient, val store: SessionStore) {

    val signedIn: Flow<Boolean> = store.accessToken.map { !it.isNullOrBlank() }
    val user: Flow<UserDto?> = store.userJson.map { json -> json?.let { runCatching { AppJson.decodeFromString(UserDto.serializer(), it) }.getOrNull() } }
    val line: Flow<LineDto?> = store.lineJson.map { json -> json?.let { runCatching { AppJson.decodeFromString(LineDto.serializer(), it) }.getOrNull() } }

    suspend fun config(): PublicConfig = api.call("GET", "/v1/config", null, PublicConfig.serializer(), auth = false)

    suspend fun signInDev(phone: String, code: String): Tokens = saveTokens(api.post<DevLogin, Tokens>("/v1/auth/dev", DevLogin(phone, code), auth = false))

    suspend fun signInFirebase(idToken: String): Tokens = saveTokens(api.post<FirebaseLogin, Tokens>("/v1/auth/firebase", FirebaseLogin(idToken), auth = false))

    private suspend fun saveTokens(tokens: Tokens): Tokens {
        store.saveTokens(tokens.accessToken, tokens.refreshToken, AppJson.encodeToString(UserDto.serializer(), tokens.user))
        store.fcmToken()?.let { registerDevice(it) }
        return tokens
    }

    suspend fun me(): UserDto = api.get<UserDto>("/v1/me").also { store.saveUser(AppJson.encodeToString(UserDto.serializer(), it)) }

    suspend fun updateMe(patch: MePatch): UserDto =
        api.patch<MePatch, UserDto>("/v1/me", patch).also { store.saveUser(AppJson.encodeToString(UserDto.serializer(), it)) }

    suspend fun registerDevice(fcmToken: String) {
        if (store.access().isNullOrBlank()) return
        api.post<DeviceBody, Unit>("/v1/devices", DeviceBody(fcmToken, BuildConfig.VERSION_NAME, "Android ${Build.VERSION.RELEASE}"))
    }

    suspend fun signOut() {
        val refresh = store.refresh()
        if (refresh != null) runCatching { api.post<RefreshBody, Unit>("/v1/auth/logout", RefreshBody(refresh)) }
        store.clearSession()
    }

    suspend fun deleteAccount() {
        api.delete("/v1/me")
        store.clearSession()
    }

    // ---- Line and forwarding
    suspend fun createLine(carrier: String?, simCount: Int, ringSeconds: Int): LineDto =
        api.post<LineBody, LineDto>("/v1/lines", LineBody(carrier, simCount, ringSeconds)).also { cacheLine(it) }

    suspend fun currentLine(): LineDto? = try {
        api.get<LineDto>("/v1/lines/current").also { cacheLine(it) }
    } catch (e: ApiException) {
        if (e.status == 404) null else throw e
    }

    suspend fun updateLine(id: String, patch: LinePatch): LineDto = api.patch<LinePatch, LineDto>("/v1/lines/$id", patch).also { cacheLine(it) }

    suspend fun startVerification(lineId: String) {
        store.saveVerifyUntil(System.currentTimeMillis() + 120_000)
        api.postEmpty<Unit>("/v1/lines/$lineId/verify")
    }

    private suspend fun cacheLine(line: LineDto) = store.saveLine(AppJson.encodeToString(LineDto.serializer(), line))

    // ---- Assistant settings
    suspend fun assistant(): AssistantDto = api.get("/v1/assistant")
    suspend fun updateAssistant(patch: AssistantPatch): AssistantDto = api.patch<AssistantPatch, AssistantDto>("/v1/assistant", patch).also { refreshPolicy() }
    suspend fun options(): AssistantOptions = api.get("/v1/assistant/options")
    suspend fun rules(): List<RuleDto> = api.get("/v1/rules")
    suspend fun saveRules(rules: List<RuleDto>): List<RuleDto> = api.put<List<RuleDto>, List<RuleDto>>("/v1/rules", rules).also { refreshPolicy() }
    suspend fun sendHint(number: String, decision: String, callerName: String? = null) =
        api.post<HintBody, Unit>("/v1/screening/hints", HintBody(number, decision, callerName))

    suspend fun reportProblem(message: String, diagnostics: Map<String, String>) =
        api.post<SupportReportBody, Unit>("/v1/support/report", SupportReportBody(message, diagnostics))

    suspend fun signalTyping(callId: String) = api.postEmpty<Unit>("/v1/calls/$callId/typing")

    suspend fun refreshPolicy(): ScreeningPolicyDto? = runCatching {
        api.get<ScreeningPolicyDto>("/v1/screening/policy").also { store.savePolicy(AppJson.encodeToString(ScreeningPolicyDto.serializer(), it)) }
    }.getOrNull()

    // ---- Calls
    suspend fun calls(query: String? = null, category: String? = null, cursor: String? = null): CallPage {
        val params = buildList {
            query?.takeIf { it.isNotBlank() }?.let { add("q=" + URLEncoder.encode(it, "UTF-8")) }
            category?.let { add("category=$it") }
            cursor?.let { add("cursor=" + URLEncoder.encode(it, "UTF-8")) }
        }
        val suffix = if (params.isEmpty()) "" else "?" + params.joinToString("&")
        return api.get("/v1/calls$suffix")
    }

    suspend fun liveCalls(): List<CallSummary> = api.get("/v1/calls/live")
    suspend fun call(id: String): CallDetail = api.get("/v1/calls/$id")
    suspend fun say(id: String, text: String) = api.post<SayBody, Unit>("/v1/calls/$id/say", SayBody(text))
    suspend fun takeOver(id: String) = api.postEmpty<Unit>("/v1/calls/$id/takeover")
    suspend fun endCall(id: String) = api.postEmpty<Unit>("/v1/calls/$id/end")
    suspend fun rate(id: String, rating: Int) = api.post<FeedbackBody, Unit>("/v1/calls/$id/feedback", FeedbackBody(rating))
    suspend fun markAction(callId: String, actionId: String, status: String) =
        api.post<ActionStatusBody, CallActionDto>("/v1/calls/$callId/actions/$actionId", ActionStatusBody(status))
    suspend fun deleteCall(id: String) = api.delete("/v1/calls/$id")
    suspend fun recordingUrl(id: String): String = api.baseUrl() + "/v1/calls/$id/recording"
    suspend fun accessToken(): String? = store.access()

    // ---- Plan and stats
    suspend fun entitlement(): Entitlement = api.get("/v1/me/entitlement")
    suspend fun stats(): Stats = api.get("/v1/me/stats")
    suspend fun verifyPurchase(productId: String, token: String): Entitlement =
        api.post<PlayPurchaseBody, Entitlement>("/v1/billing/google-play", PlayPurchaseBody(productId, token))

    // ---- Assistant chat and outbound calls
    suspend fun chatHistory(): List<ChatMessageDto> = api.get("/v1/assistant/chat")
    suspend fun chat(text: String): ChatReply = api.post<ChatBody, ChatReply>("/v1/assistant/chat", ChatBody(text))
    suspend fun outbound(): List<OutboundDto> = api.get("/v1/outbound")
    suspend fun scheduleCall(body: OutboundBody): OutboundDto = api.post<OutboundBody, OutboundDto>("/v1/outbound", body)
    suspend fun cancelOutbound(id: String) = api.delete("/v1/outbound/$id")
}
