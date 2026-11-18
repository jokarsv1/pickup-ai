"""Database tables. Types are kept portable so tests run on SQLite and production on Postgres."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("usr"))
    phone_e164: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(12), default="en-IN")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    trial_ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free | pro
    plan_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("dev"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fcm_token: Mapped[str] = mapped_column(String(512), unique=True)
    platform: Mapped[str] = mapped_column(String(16), default="android")
    app_version: Mapped[str | None] = mapped_column(String(32))
    os_version: Mapped[str | None] = mapped_column(String(32))
    # iPhone: token that lets the server start a Live Activity when a call begins (iOS 17.2+)
    live_activity_start_token: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class NumberPoolEntry(Base):
    """Virtual numbers rented from the telephony provider. Each user gets one."""

    __tablename__ = "number_pool"
    number: Mapped[str] = mapped_column(String(20), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    region: Mapped[str] = mapped_column(String(8), default="IN")
    state: Mapped[str] = mapped_column(String(16), default="free")  # free | assigned | quarantine
    user_id: Mapped[str | None] = mapped_column(String(40), index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    quarantine_until: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Line(Base):
    """The user's own SIM number and how it forwards to their assistant number."""

    __tablename__ = "lines"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("line"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    phone_e164: Mapped[str] = mapped_column(String(20))
    carrier: Mapped[str | None] = mapped_column(String(40))
    sim_count: Mapped[int] = mapped_column(Integer, default=1)
    assistant_number: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | verified | broken | released
    ring_seconds: Mapped[int] = mapped_column(Integer, default=20)
    verification_pending_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_forwarded_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Calls the phone sent on that never arrived, in a row: carriers silently drop forwarding.
    missed_streak: Mapped[int] = mapped_column(Integer, default=0)
    forwarding_alert_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AssistantSettings(Base):
    __tablename__ = "assistant_settings"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    assistant_name: Mapped[str] = mapped_column(String(40), default="Pickup")
    voice: Mapped[str] = mapped_column(String(40), default="ritu")
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["en-IN", "hi-IN"])
    greeting: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text, default="")
    pack_ids: Mapped[list] = mapped_column(JSON, default=lambda: ["deliveries", "sales_calls", "banks"])
    screening_mode: Mapped[str] = mapped_column(String(20), default="assistant_first")  # assistant_first | ring_first | off
    screen_contacts: Mapped[bool] = mapped_column(Boolean, default=False)
    snooze_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    record_calls: Mapped[bool] = mapped_column(Boolean, default=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    urgent_passthrough: Mapped[bool] = mapped_column(Boolean, default=True)
    share_location_with_deliveries: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_note: Mapped[str | None] = mapped_column(Text)
    # Banks, insurers and government (1600) and service calls (1601) ring instead of going to the assistant.
    ring_verified_business: Mapped[bool] = mapped_column(Boolean, default=True)
    # The same number calling twice within a few minutes rings: urgent callers try again.
    ring_repeat_callers: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rule"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_type: Mapped[str] = mapped_column(String(16))  # number | category
    match_value: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))  # handle | ring_me | decline | connect
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ContactEntry(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("con"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    number_e164: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("user_id", "number_e164", name="uq_contact_user_number"),)


class ScreeningHint(Base):
    """Sent by the phone right before it declines a call, so the backend knows the true caller."""

    __tablename__ = "screening_hints"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("hint"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    caller_number: Mapped[str] = mapped_column(String(20))
    # The contact's name from the phone's address book, for this one call (contacts never upload).
    caller_name: Mapped[str | None] = mapped_column(String(120))
    decision: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class SupportReport(Base):
    """"Report a problem" from the app, with the setup details we'd otherwise have to ask for."""

    __tablename__ = "support_reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("sup"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text)
    diagnostics: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | answered | closed
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Call(Base):
    __tablename__ = "calls"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("call"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    line_id: Mapped[str | None] = mapped_column(String(40))
    direction: Mapped[str] = mapped_column(String(10), default="inbound")  # inbound | outbound
    mode: Mapped[str] = mapped_column(String(16), default="screen")  # screen | demo | outbound | message_only
    provider: Mapped[str] = mapped_column(String(16))
    provider_call_id: Mapped[str | None] = mapped_column(String(80), index=True)
    from_number: Mapped[str | None] = mapped_column(String(20))
    to_number: Mapped[str | None] = mapped_column(String(20))
    caller_known_name: Mapped[str | None] = mapped_column(String(120))  # from the user's contacts
    caller_name: Mapped[str | None] = mapped_column(String(120))  # what the caller said
    caller_org: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str | None] = mapped_column(String(10))
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_replies: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16), default="ringing")
    takeover_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    end_reason: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    taken_over_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    recording_key: Mapped[str | None] = mapped_column(String(200))
    rating: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)
    outbound_task_id: Mapped[str | None] = mapped_column(String(40))
    # iPhone: token for updating this call's Live Activity (Lock Screen / Dynamic Island)
    live_activity_token: Mapped[str | None] = mapped_column(String(256))
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_calls_user_started", "user_id", "started_at"),)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(12))  # caller | assistant | owner | system
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class CallAction(Base):
    __tablename__ = "call_actions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("act"))
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(16))  # reminder | call_back | save_contact | block
    title: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | done | dismissed


class OutboundTask(Base):
    __tablename__ = "outbound_tasks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("obt"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_number: Mapped[str] = mapped_column(String(20))
    to_name: Mapped[str | None] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    state: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled | dialing | done | failed | cancelled
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    call_id: Mapped[str | None] = mapped_column(String(40))
    result_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    text: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[list] = mapped_column(JSON, default=list)  # full API content blocks, replayed verbatim
    client_actions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class NumberReputation(Base):
    """Aggregated across all users, keyed by a salted hash so raw caller numbers are not shared."""

    __tablename__ = "number_reputation"
    number_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    spam_calls: Mapped[int] = mapped_column(Integer, default=0)
    category_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    top_org: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("pur"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String(80))
    purchase_token: Mapped[str] = mapped_column(String(512), unique=True)
    state: Mapped[str] = mapped_column(String(24))
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
