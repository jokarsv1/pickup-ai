package ai.pickup.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// Mirrors backend/app/schemas.py. Timestamps stay ISO-8601 strings and are parsed for display.

@Serializable
data class PublicConfig(
    @SerialName("auth_modes") val authModes: List<String> = emptyList(),
    @SerialName("dev_code_hint") val devCodeHint: String? = null,
    @SerialName("telephony_provider") val telephonyProvider: String = "",
    @SerialName("voice_ready") val voiceReady: Boolean = false,
    @SerialName("missing_keys") val missingKeys: List<String> = emptyList(),
    @SerialName("play_products") val playProducts: List<String> = emptyList(),
)

@Serializable
data class UserDto(
    val id: String,
    val phone: String,
    val name: String? = null,
    val language: String = "en-IN",
    val plan: String = "free",
    @SerialName("onboarding_completed") val onboardingCompleted: Boolean = false,
)

@Serializable
data class Tokens(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("expires_in") val expiresIn: Int,
    val user: UserDto,
    @SerialName("is_new_user") val isNewUser: Boolean,
)

@Serializable
data class DevLogin(val phone: String, val code: String)

@Serializable
data class FirebaseLogin(@SerialName("id_token") val idToken: String)

@Serializable
data class RefreshBody(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class MePatch(
    val name: String? = null,
    val language: String? = null,
    @SerialName("onboarding_completed") val onboardingCompleted: Boolean? = null,
)

@Serializable
data class DeviceBody(
    @SerialName("fcm_token") val fcmToken: String,
    @SerialName("app_version") val appVersion: String? = null,
    @SerialName("os_version") val osVersion: String? = null,
)

@Serializable
data class ForwardingCode(val key: String, val title: String, val description: String, val code: String)

@Serializable
data class LineDto(
    val id: String,
    val phone: String,
    @SerialName("assistant_number") val assistantNumber: String,
    @SerialName("assistant_number_display") val assistantNumberDisplay: String,
    val status: String,
    val carrier: String? = null,
    @SerialName("carrier_note") val carrierNote: String? = null,
    @SerialName("ring_seconds") val ringSeconds: Int = 20,
    @SerialName("verified_at") val verifiedAt: String? = null,
    @SerialName("last_forwarded_at") val lastForwardedAt: String? = null,
    @SerialName("activation_codes") val activationCodes: List<ForwardingCode> = emptyList(),
    @SerialName("deactivation_code") val deactivationCode: String = "##004#",
    @SerialName("deactivation_all_code") val deactivationAllCode: String = "##002#",
)

@Serializable
data class LineBody(
    val carrier: String? = null,
    @SerialName("sim_count") val simCount: Int = 1,
    @SerialName("ring_seconds") val ringSeconds: Int = 20,
)

@Serializable
data class LinePatch(@SerialName("ring_seconds") val ringSeconds: Int? = null, @SerialName("sim_count") val simCount: Int? = null)

@Serializable
data class AssistantDto(
    @SerialName("assistant_name") val assistantName: String = "Pickup",
    val voice: String = "ritu",
    val languages: List<String> = listOf("en-IN"),
    val greeting: String? = null,
    val instructions: String = "",
    @SerialName("pack_ids") val packIds: List<String> = emptyList(),
    @SerialName("screening_mode") val screeningMode: String = "assistant_first",
    @SerialName("screen_contacts") val screenContacts: Boolean = false,
    @SerialName("snooze_until") val snoozeUntil: String? = null,
    @SerialName("record_calls") val recordCalls: Boolean = true,
    @SerialName("retention_days") val retentionDays: Int = 90,
    @SerialName("urgent_passthrough") val urgentPassthrough: Boolean = true,
    @SerialName("delivery_note") val deliveryNote: String? = null,
)

@Serializable
data class AssistantPatch(
    @SerialName("assistant_name") val assistantName: String? = null,
    val voice: String? = null,
    val languages: List<String>? = null,
    val greeting: String? = null,
    val instructions: String? = null,
    @SerialName("pack_ids") val packIds: List<String>? = null,
    @SerialName("screening_mode") val screeningMode: String? = null,
    @SerialName("screen_contacts") val screenContacts: Boolean? = null,
    @SerialName("snooze_minutes") val snoozeMinutes: Int? = null,
    @SerialName("record_calls") val recordCalls: Boolean? = null,
    @SerialName("retention_days") val retentionDays: Int? = null,
    @SerialName("urgent_passthrough") val urgentPassthrough: Boolean? = null,
    @SerialName("delivery_note") val deliveryNote: String? = null,
)

@Serializable
data class Pack(val id: String, val title: String, val subtitle: String, val instructions: String)

@Serializable
data class VoiceOption(val id: String, val label: String)

@Serializable
data class AssistantOptions(
    val packs: List<Pack> = emptyList(),
    val categories: Map<String, String> = emptyMap(),
    val voices: List<VoiceOption> = emptyList(),
    val languages: Map<String, String> = emptyMap(),
)

@Serializable
data class RuleDto(
    val id: String? = null,
    @SerialName("match_type") val matchType: String,
    @SerialName("match_value") val matchValue: String,
    val action: String,
    val note: String? = null,
)

@Serializable
data class ContactBody(val name: String, val numbers: List<String>)

@Serializable
data class ContactsSyncBody(val contacts: List<ContactBody>, val replace: Boolean = true)

@Serializable
data class HintBody(@SerialName("caller_number") val callerNumber: String, val decision: String = "declined")

@Serializable
data class ScreeningPolicyDto(
    @SerialName("screening_mode") val screeningMode: String = "assistant_first",
    @SerialName("screen_contacts") val screenContacts: Boolean = false,
    @SerialName("snooze_until") val snoozeUntil: String? = null,
    @SerialName("line_status") val lineStatus: String = "none",
    @SerialName("assistant_number") val assistantNumber: String? = null,
    @SerialName("always_ring") val alwaysRing: List<String> = emptyList(),
    @SerialName("always_screen") val alwaysScreen: List<String> = emptyList(),
)

@Serializable
data class CallSummary(
    val id: String,
    val direction: String = "inbound",
    val mode: String = "screen",
    val state: String,
    val title: String,
    @SerialName("caller_number") val callerNumber: String? = null,
    @SerialName("caller_known_name") val callerKnownName: String? = null,
    @SerialName("caller_name") val callerName: String? = null,
    @SerialName("caller_org") val callerOrg: String? = null,
    val category: String? = null,
    @SerialName("category_label") val categoryLabel: String? = null,
    val reason: String? = null,
    val summary: String? = null,
    val urgency: String? = null,
    @SerialName("is_spam") val isSpam: Boolean = false,
    @SerialName("started_at") val startedAt: String,
    @SerialName("duration_seconds") val durationSeconds: Int? = null,
    @SerialName("has_recording") val hasRecording: Boolean = false,
    val unread: Boolean = false,
)

@Serializable
data class TranscriptLine(val seq: Int, val speaker: String, val text: String, val at: String = "")

@Serializable
data class CallActionDto(
    val id: String,
    val type: String,
    val title: String,
    val payload: JsonObject = JsonObject(emptyMap()),
    val status: String = "open",
)

@Serializable
data class CallDetail(
    val id: String,
    val direction: String = "inbound",
    val mode: String = "screen",
    val state: String,
    val title: String,
    @SerialName("caller_number") val callerNumber: String? = null,
    @SerialName("caller_known_name") val callerKnownName: String? = null,
    @SerialName("caller_name") val callerName: String? = null,
    @SerialName("caller_org") val callerOrg: String? = null,
    val category: String? = null,
    @SerialName("category_label") val categoryLabel: String? = null,
    val reason: String? = null,
    val summary: String? = null,
    val urgency: String? = null,
    @SerialName("is_spam") val isSpam: Boolean = false,
    @SerialName("started_at") val startedAt: String,
    @SerialName("duration_seconds") val durationSeconds: Int? = null,
    @SerialName("has_recording") val hasRecording: Boolean = false,
    val unread: Boolean = false,
    @SerialName("suggested_replies") val suggestedReplies: List<String> = emptyList(),
    val transcript: List<TranscriptLine> = emptyList(),
    val actions: List<CallActionDto> = emptyList(),
    val rating: Int? = null,
    @SerialName("end_reason") val endReason: String? = null,
)

@Serializable
data class CallPage(val items: List<CallSummary> = emptyList(), @SerialName("next_cursor") val nextCursor: String? = null)

@Serializable
data class SayBody(val text: String)

@Serializable
data class FeedbackBody(val rating: Int, val comment: String? = null)

@Serializable
data class ActionStatusBody(val status: String)

@Serializable
data class Entitlement(
    val level: String = "free",
    @SerialName("live_controls") val liveControls: Boolean = false,
    @SerialName("outbound_calls") val outboundCalls: Boolean = false,
    val recordings: Boolean = false,
    @SerialName("calls_left_this_month") val callsLeftThisMonth: Int? = null,
    @SerialName("trial_ends_at") val trialEndsAt: String? = null,
    @SerialName("plan_expires_at") val planExpiresAt: String? = null,
)

@Serializable
data class Stats(
    @SerialName("calls_handled") val callsHandled: Int = 0,
    @SerialName("spam_blocked") val spamBlocked: Int = 0,
    @SerialName("minutes_saved") val minutesSaved: Int = 0,
    @SerialName("calls_this_week") val callsThisWeek: Int = 0,
)

@Serializable
data class ChatBody(val text: String)

@Serializable
data class ChatMessageDto(
    val id: Long,
    val role: String,
    val text: String,
    @SerialName("client_actions") val clientActions: List<JsonObject> = emptyList(),
    val at: String = "",
)

@Serializable
data class ChatReply(
    val reply: String,
    @SerialName("client_actions") val clientActions: List<JsonObject> = emptyList(),
    val messages: List<ChatMessageDto> = emptyList(),
)

@Serializable
data class OutboundDto(
    val id: String,
    @SerialName("to_number") val toNumber: String,
    @SerialName("to_name") val toName: String? = null,
    val goal: String,
    @SerialName("scheduled_at") val scheduledAt: String,
    val state: String,
    @SerialName("call_id") val callId: String? = null,
    @SerialName("result_summary") val resultSummary: String? = null,
)

@Serializable
data class OutboundBody(
    @SerialName("to_number") val toNumber: String,
    @SerialName("to_name") val toName: String? = null,
    val goal: String,
    @SerialName("scheduled_at") val scheduledAt: String? = null,
)

@Serializable
data class PlayPurchaseBody(@SerialName("product_id") val productId: String, @SerialName("purchase_token") val purchaseToken: String)

@Serializable
data class TicketDto(val ticket: String)

@Serializable
data class ErrorBody(val detail: kotlinx.serialization.json.JsonElement? = null)
