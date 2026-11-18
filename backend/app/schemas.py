"""Request and response bodies for the mobile API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PublicConfig(BaseModel):
    auth_modes: list[str]
    dev_code_hint: str | None
    telephony_provider: str
    voice_ready: bool
    missing_keys: list[str]
    min_app_version: int = 1
    support_email: str = "support@pickup.ai"
    play_products: list[str]


class FirebaseLogin(BaseModel):
    id_token: str


class DevLogin(BaseModel):
    phone: str
    code: str


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    phone: str
    name: str | None
    language: str
    plan: str
    onboarding_completed: bool


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut
    is_new_user: bool


class MeUpdate(BaseModel):
    name: str | None = Field(None, max_length=80)
    language: str | None = None
    onboarding_completed: bool | None = None


class DeviceIn(BaseModel):
    fcm_token: str = Field(..., max_length=512)  # FCM token on Android, APNs device token on iPhone
    platform: Literal["android", "ios"] = "android"
    live_activity_start_token: str | None = Field(None, max_length=256)  # iPhone, iOS 17.2+
    app_version: str | None = None
    os_version: str | None = None


class EntitlementOut(BaseModel):
    level: str
    live_controls: bool
    outbound_calls: bool
    recordings: bool
    calls_left_this_month: int | None
    trial_ends_at: datetime | None
    plan_expires_at: datetime | None


class LineIn(BaseModel):
    phone: str | None = None  # defaults to the signed-in phone number
    carrier: str | None = None
    sim_count: int = 1
    ring_seconds: int = 20


class ForwardingCodeOut(BaseModel):
    key: str
    title: str
    description: str
    code: str


class LineOut(BaseModel):
    id: str
    phone: str
    assistant_number: str
    assistant_number_display: str
    status: str
    carrier: str | None
    carrier_note: str | None
    ring_seconds: int
    verified_at: datetime | None
    last_forwarded_at: datetime | None
    # Calls the phone sent to the assistant that never arrived, in a row (carrier dropped forwarding).
    missed_streak: int = 0
    forwarding_problem: bool = False
    sim_count: int = 1
    activation_codes: list[ForwardingCodeOut]
    deactivation_code: str
    deactivation_all_code: str


class LineUpdate(BaseModel):
    ring_seconds: int | None = Field(None, ge=5, le=30)
    carrier: str | None = None
    sim_count: int | None = None


class AssistantOut(BaseModel):
    assistant_name: str
    voice: str
    languages: list[str]
    greeting: str | None
    instructions: str
    pack_ids: list[str]
    screening_mode: str
    screen_contacts: bool
    snooze_until: datetime | None
    record_calls: bool
    retention_days: int
    urgent_passthrough: bool
    delivery_note: str | None
    ring_verified_business: bool = True
    ring_repeat_callers: bool = True


class AssistantUpdate(BaseModel):
    assistant_name: str | None = Field(None, max_length=40)
    voice: str | None = None
    languages: list[str] | None = None
    greeting: str | None = Field(None, max_length=300)
    instructions: str | None = Field(None, max_length=4000)
    pack_ids: list[str] | None = None
    screening_mode: Literal["assistant_first", "ring_first", "off"] | None = None
    screen_contacts: bool | None = None
    snooze_minutes: int | None = Field(None, ge=0, le=24 * 60)
    record_calls: bool | None = None
    retention_days: int | None = Field(None, ge=1, le=365)
    urgent_passthrough: bool | None = None
    delivery_note: str | None = Field(None, max_length=300)
    ring_verified_business: bool | None = None
    ring_repeat_callers: bool | None = None


class PackOut(BaseModel):
    id: str
    title: str
    subtitle: str
    instructions: str


class VoiceOut(BaseModel):
    id: str
    label: str


class OptionsOut(BaseModel):
    packs: list[PackOut]
    categories: dict[str, str]
    voices: list[VoiceOut]
    languages: dict[str, str]


class RuleIn(BaseModel):
    match_type: Literal["number", "category"]
    match_value: str = Field(..., max_length=64)
    action: Literal["handle", "ring_me", "decline", "connect"]
    note: str | None = Field(None, max_length=200)


class RuleOut(RuleIn):
    id: str


class ContactIn(BaseModel):
    name: str = Field(..., max_length=120)
    numbers: list[str]


class ContactsSync(BaseModel):
    contacts: list[ContactIn] = Field(..., max_length=20000)
    replace: bool = True


class ScreeningHintIn(BaseModel):
    caller_number: str
    decision: Literal["declined", "allowed", "silenced"] = "declined"
    # Only for a saved contact the user chose to screen: their name, for this call alone.
    caller_name: str | None = Field(None, max_length=120)


class SupportReportIn(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    diagnostics: dict[str, str | int | bool | None] = Field(default_factory=dict, max_length=40)


class SupportReportOut(BaseModel):
    id: str
    created_at: datetime


class TranscriptLine(BaseModel):
    seq: int
    speaker: str
    text: str
    at: datetime


class ActionOut(BaseModel):
    id: str
    type: str
    title: str
    payload: dict
    status: str


class CallSummaryOut(BaseModel):
    id: str
    direction: str
    mode: str
    state: str
    title: str
    caller_number: str | None
    caller_known_name: str | None
    caller_name: str | None
    caller_org: str | None
    category: str | None
    category_label: str | None
    reason: str | None
    summary: str | None
    urgency: str | None
    is_spam: bool
    # TRAI's regulated business series: "Verified bank or government number" and so on.
    caller_label: str | None = None
    started_at: datetime
    duration_seconds: int | None
    has_recording: bool
    unread: bool


class CallDetailOut(CallSummaryOut):
    suggested_replies: list[str]
    transcript: list[TranscriptLine]
    actions: list[ActionOut]
    rating: int | None
    end_reason: str | None


class CallPage(BaseModel):
    items: list[CallSummaryOut]
    next_cursor: str | None


class SayIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)


class FeedbackIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)


class ActionUpdate(BaseModel):
    status: Literal["done", "dismissed", "open"]


class ChatIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    id: int
    role: str
    text: str
    client_actions: list[dict]
    at: datetime


class ChatReply(BaseModel):
    reply: str
    client_actions: list[dict]
    messages: list[ChatMessageOut]


class OutboundIn(BaseModel):
    to_number: str
    to_name: str | None = None
    goal: str = Field(..., min_length=5, max_length=1000)
    scheduled_at: datetime | None = None


class OutboundOut(BaseModel):
    id: str
    to_number: str
    to_name: str | None
    goal: str
    scheduled_at: datetime
    state: str
    call_id: str | None
    result_summary: str | None


class PlayPurchaseIn(BaseModel):
    product_id: str
    purchase_token: str


class StatsOut(BaseModel):
    calls_handled: int
    spam_blocked: int
    minutes_saved: int
    calls_this_week: int


class NumberIn(BaseModel):
    number: str
    provider: Literal["exotel", "plivo", "twilio"]
    region: str = "IN"


class LiveActivityTokenIn(BaseModel):
    token: str = Field(..., min_length=8, max_length=256)
