"""Call lifecycle: routing a forwarded call, live updates, and closing it out."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import CallInsights, LiveIntent
from app.db import sessionmaker, utcnow
from app.entitlements import entitlement_for
from app.events import bus, user_topic
from app.models import (
    Call,
    CallAction,
    Line,
    NumberPoolEntry,
    NumberReputation,
    ScreeningHint,
    TranscriptSegment,
    User,
)
from app.packs import CATEGORIES
from app.phone import SERIES_LABELS, designated_series, normalize, pretty, reputation_hash
from app.push import Throttle, get_push

HINT_WINDOW = timedelta(seconds=90)
# A call the phone sent on that hasn't arrived after this long never will: the carrier dropped it.
UNREACHED_AFTER = timedelta(seconds=75)
# This many in a row and we tell the user their forwarding needs re-dialling.
FORWARDING_PROBLEM_STREAK = 2
FORWARDING_ALERT_EVERY = timedelta(hours=12)


def aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@dataclass
class RouteDecision:
    kind: Literal["agent", "verified", "reject_loop", "unknown_number"]
    call_id: str | None = None
    say: str | None = None


async def is_system_number(session: AsyncSession, number: str | None) -> bool:
    if not number:
        return False
    return (await session.get(NumberPoolEntry, number)) is not None


async def route_inbound(
    session: AsyncSession, *, provider: str, provider_call_id: str | None, from_raw: str | None, to_raw: str | None, direction: str = "inbound"
) -> RouteDecision:
    """Decide what happens to a call that reached one of our assistant numbers."""
    to_number = normalize(to_raw)
    from_number = normalize(from_raw)
    line = await session.scalar(select(Line).where(Line.assistant_number == to_number, Line.status != "released"))
    if line is None:
        logger.warning(f"Call to unassigned number {to_raw}")
        return RouteDecision("unknown_number", say="Sorry, this number is not in service.")

    now = utcnow()
    if await is_system_number(session, from_number):
        if line.verification_pending_until and aware(line.verification_pending_until) > now:
            line.status = "verified"
            line.verified_at = now
            line.last_forwarded_at = now
            line.verification_pending_until = None
            await session.commit()
            await notify(line.user_id, {"type": "line.verified", "line_id": line.id}, push=True)
            return RouteDecision("verified", say="Your Pickup assistant is set up. You can hang up now.")
        # Our own number calling our own number: a take-over transfer the user didn't answer,
        # bounced back by their forwarding. Never let the AI answer itself.
        return RouteDecision("reject_loop", say="Sorry, they're not able to join right now. Goodbye.")

    user = await session.get(User, line.user_id)
    assert user is not None
    caller = from_number
    mode = "screen"
    hint: ScreeningHint | None = None
    if from_number and from_number == line.phone_e164:
        hint = await _take_recent_hint(session, user.id, now)
        if hint is not None:
            caller = hint.caller_number  # carrier showed the forwarding number; the phone told us the real one
        else:
            mode = "demo"  # the user is calling their own assistant to try it
    elif from_number:
        hint = await _take_recent_hint(session, user.id, now, caller_number=from_number)

    if mode == "screen":
        ent = await entitlement_for(session, user)
        if ent.level == "limited":
            mode = "message_only"

    # A saved contact's name comes from the phone with this call's hint; address books never upload.
    known_name = hint.caller_name if hint is not None and hint.caller_number == caller else None
    line.last_forwarded_at = now
    if mode != "demo":
        line.missed_streak = 0  # forwarding works
    if line.status == "pending" and mode == "screen":
        line.status = "verified"  # a real forwarded call proves forwarding works
        line.verified_at = now
    call = Call(
        user_id=user.id,
        line_id=line.id,
        direction=direction,
        mode=mode,
        provider=provider,
        provider_call_id=provider_call_id,
        from_number=caller,
        to_number=to_number,
        caller_known_name=known_name,
        state="ringing",
    )
    session.add(call)
    await session.commit()
    await notify(
        user.id,
        {
            "type": "call.started",
            "call_id": call.id,
            "mode": mode,
            "caller_number": caller,
            "caller_display": known_name or pretty(caller),
            "started_at": call.started_at.isoformat(),
        },
        push=mode != "demo",
    )
    return RouteDecision("agent", call_id=call.id)


async def _take_recent_hint(
    session: AsyncSession, user_id: str, now: datetime, caller_number: str | None = None
) -> ScreeningHint | None:
    q = select(ScreeningHint).where(
        ScreeningHint.user_id == user_id, ScreeningHint.consumed.is_(False), ScreeningHint.created_at >= now - HINT_WINDOW
    )
    if caller_number:
        q = q.where(ScreeningHint.caller_number == caller_number)
    hint = await session.scalar(q.order_by(ScreeningHint.created_at.desc()).limit(1))
    if hint is not None:
        hint.consumed = True
    return hint


async def notify(user_id: str, event: dict[str, Any], *, push: bool = False, collapse_key: str | None = None) -> None:
    await bus.publish(user_topic(user_id), event)
    if push:
        try:
            await get_push().send_to_user(user_id, event, collapse_key=collapse_key)
        except Exception as exc:  # push must never break a call
            logger.warning(f"Push failed: {exc}")


_live_throttle: Throttle | None = None


def live_throttle() -> Throttle:
    global _live_throttle
    if _live_throttle is None:
        _live_throttle = Throttle(get_push(), interval=1.5)
    return _live_throttle


async def push_live_snapshot(call_id: str) -> None:
    """Update the single live-call notification: caller, reason, last lines, smart replies."""
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None or call.mode == "demo":
            return
        rows = (
            await session.execute(
                select(TranscriptSegment.speaker, TranscriptSegment.text)
                .where(TranscriptSegment.call_id == call_id)
                .order_by(TranscriptSegment.seq.desc())
                .limit(4)
            )
        ).all()
    data = {
        "type": "call.live",
        "call_id": call.id,
        "title": display_title(call),
        "reason": call.reason or "",
        "category": call.category or "",
        "state": call.state,
        "lines": [{"s": s, "t": t} for s, t in reversed(rows)],
        "replies": call.suggested_replies or [],
    }
    try:
        await live_throttle().send(call.id, call.user_id, data, collapse_key=call.id)
    except Exception as exc:
        logger.warning(f"Live push failed: {exc}")


def display_title(call: Call) -> str:
    who = call.caller_known_name or call.caller_name
    if who and call.caller_org:
        return f"{who} · {call.caller_org}"
    if who:
        return who
    if call.caller_org:
        return call.caller_org
    return pretty(call.from_number)


async def append_transcript(call_id: str, speaker: str, text: str) -> int:
    text = text.strip()
    if not text:
        return -1
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return -1
        seq = int((await session.scalar(select(func.count(TranscriptSegment.id)).where(TranscriptSegment.call_id == call_id))) or 0)
        session.add(TranscriptSegment(call_id=call_id, seq=seq, speaker=speaker, text=text))
        await session.commit()
        user_id = call.user_id
    await bus.publish(user_topic(user_id), {"type": "transcript", "call_id": call_id, "seq": seq, "speaker": speaker, "text": text})
    await push_live_snapshot(call_id)
    return seq


async def transcript_pairs(session: AsyncSession, call_id: str) -> list[tuple[str, str]]:
    rows = (
        await session.execute(
            select(TranscriptSegment.speaker, TranscriptSegment.text).where(TranscriptSegment.call_id == call_id).order_by(TranscriptSegment.seq)
        )
    ).all()
    return [(s, t) for s, t in rows]


async def set_state(call_id: str, state: str, **fields: Any) -> Call | None:
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return None
        call.state = state
        for key, value in fields.items():
            setattr(call, key, value)
        await session.commit()
    await bus.publish(user_topic(call.user_id), {"type": "call.state", "call_id": call_id, "state": state})
    return call


async def apply_intent(call_id: str, intent: LiveIntent) -> None:
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return
        call.caller_name = intent.caller_name or call.caller_name
        call.caller_org = intent.organisation or call.caller_org
        call.category = intent.category
        call.reason = intent.reason
        call.urgency = intent.urgency
        call.is_spam = intent.is_spam and designated_series(call.from_number) is None
        call.suggested_replies = intent.suggested_replies[:3]
        await session.commit()
        event = {
            "type": "intent",
            "call_id": call_id,
            "title": display_title(call),
            "caller_name": call.caller_name,
            "organisation": call.caller_org,
            "category": call.category,
            "category_label": CATEGORIES.get(call.category or "other", "Other"),
            "reason": call.reason,
            "urgency": call.urgency,
            "is_spam": call.is_spam,
            "suggested_replies": call.suggested_replies,
        }
        user_id = call.user_id
    await bus.publish(user_topic(user_id), event)
    await push_live_snapshot(call_id)


async def finish_call(call_id: str, end_reason: str, recording_key: str | None = None) -> Call | None:
    now = utcnow()
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return None
        if call.ended_at is None:
            call.ended_at = now
            start = aware(call.answered_at) or aware(call.started_at) or now
            call.duration_seconds = max(0, int((now - start).total_seconds()))
        call.end_reason = call.end_reason or end_reason
        call.state = "processing" if call.mode != "demo" else "ended"
        if recording_key:
            call.recording_key = recording_key
        await session.commit()
        payload = {"type": "call.ended", "call_id": call_id, "title": display_title(call), "duration": call.duration_seconds, "end_reason": call.end_reason}
        user_id = call.user_id
        push = call.mode != "demo"
    await notify(user_id, payload, push=push, collapse_key=call_id)
    return call


async def apply_insights(call_id: str, insights: CallInsights) -> None:
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return
        call.caller_name = insights.caller_name or call.caller_name
        call.caller_org = insights.organisation or call.caller_org
        call.category = insights.category
        call.reason = insights.reason
        call.summary = insights.summary
        call.urgency = insights.urgency
        series = designated_series(call.from_number)
        call.is_spam = insights.is_spam and series is None  # TRAI: regulated series are never tagged spam
        call.state = "summarized"
        actions: list[CallAction] = []
        for action in insights.actions[:3]:
            if action.type == "block" and series is not None:
                continue
            payload: dict[str, Any] = {}
            if action.due_at:
                payload["due_at"] = action.due_at
            number = normalize(action.number) if action.number else call.from_number
            if action.type in ("call_back", "save_contact", "block") and number:
                payload["number"] = number
            if action.type == "save_contact":
                if call.caller_known_name:
                    continue  # already a contact
                payload["name"] = action.contact_name or insights.caller_name or ""
            actions.append(CallAction(call_id=call_id, user_id=call.user_id, type=action.type, title=action.title, payload=payload))
        session.add_all(actions)
        if call.from_number and series is None:
            await _update_reputation(session, call.from_number, insights)
        await session.commit()
        event = {
            "type": "summary",
            "call_id": call_id,
            "title": display_title(call),
            "summary": call.summary,
            "category": call.category,
            "urgency": call.urgency,
            "is_spam": call.is_spam,
            "actions": [{"id": a.id, "type": a.type, "title": a.title, "payload": a.payload} for a in actions],
        }
        user_id = call.user_id
        mode = call.mode
    await notify(user_id, event, push=mode != "demo", collapse_key=call_id)


async def _update_reputation(session: AsyncSession, number: str, insights: CallInsights) -> None:
    key = reputation_hash(number)
    rep = await session.get(NumberReputation, key)
    if rep is None:
        rep = NumberReputation(number_hash=key, total_calls=0, spam_calls=0, category_counts={})
        session.add(rep)
    rep.total_calls = (rep.total_calls or 0) + 1
    if insights.is_spam:
        rep.spam_calls = (rep.spam_calls or 0) + 1
    counts = dict(rep.category_counts or {})
    counts[insights.category] = counts.get(insights.category, 0) + 1
    rep.category_counts = counts
    if insights.organisation:
        rep.top_org = insights.organisation


async def reputation_note(session: AsyncSession, number: str | None) -> str | None:
    if not number:
        return None
    series = designated_series(number)
    if series is not None:
        return f"This is a {SERIES_LABELS[series].lower()} registered with TRAI, not spam."
    rep = await session.get(NumberReputation, reputation_hash(number))
    if rep is None or not rep.total_calls:
        return None
    parts = []
    if rep.spam_calls and rep.spam_calls / rep.total_calls >= 0.5 and rep.total_calls >= 3:
        parts.append(f"Other Pickup users flagged this number as spam in {rep.spam_calls} of {rep.total_calls} calls.")
    if rep.category_counts:
        top = max(rep.category_counts.items(), key=lambda kv: kv[1])[0]
        parts.append(f"It usually calls about: {CATEGORIES.get(top, top)}.")
    if rep.top_org:
        parts.append(f"Often identifies as {rep.top_org}.")
    return " ".join(parts) or None


async def sweep_unreached(now: datetime | None = None) -> int:
    """Turns calls the phone sent on, but that never reached the assistant, into missed calls.

    Carriers silently drop 30-40% of forwarded calls and sometimes forget forwarding altogether.
    Without this the user would never know someone called. After a few in a row, we tell them
    to re-dial their forwarding code.
    """
    now = now or utcnow()
    events: list[tuple[str, dict, dict | None]] = []
    async with sessionmaker()() as session:
        hints = (
            await session.scalars(
                select(ScreeningHint)
                .where(ScreeningHint.consumed.is_(False), ScreeningHint.decision == "declined", ScreeningHint.created_at < now - UNREACHED_AFTER)
                .order_by(ScreeningHint.created_at)
                .limit(200)
            )
        ).all()
        for hint in hints:
            hint.consumed = True
            created = aware(hint.created_at) or now
            if created < now - timedelta(hours=6):
                continue  # stale (the server was down): don't flood the user
            if await is_system_number(session, hint.caller_number):
                continue  # our own forwarding test or a take-over transfer
            line = await session.scalar(
                select(Line).where(Line.user_id == hint.user_id, Line.status != "released").order_by(Line.created_at.desc())
            )
            if line is None:
                continue
            who = hint.caller_name or pretty(hint.caller_number)
            call = Call(
                user_id=hint.user_id,
                line_id=line.id,
                direction="inbound",
                mode="not_reached",
                provider="carrier",
                from_number=hint.caller_number,
                to_number=line.assistant_number,
                caller_known_name=hint.caller_name,
                state="summarized",
                started_at=created,
                ended_at=created,
                duration_seconds=0,
                end_reason="not_forwarded",
                reason="Didn't reach your assistant",
                summary=(
                    f"{who} called, but the call didn't reach your assistant: your carrier didn't forward it, "
                    "or they hung up while it was being forwarded. Call back if you need to."
                ),
            )
            session.add(call)
            line.missed_streak = (line.missed_streak or 0) + 1
            alert = None
            due = line.forwarding_alert_at is None or (aware(line.forwarding_alert_at) or now) < now - FORWARDING_ALERT_EVERY
            if line.missed_streak >= FORWARDING_PROBLEM_STREAK and due:
                line.forwarding_alert_at = now
                alert = {"type": "forwarding.problem", "line_id": line.id, "missed": line.missed_streak}
            await session.flush()
            missed = {
                "type": "call.missed",
                "call_id": call.id,
                "title": display_title(call),
                "caller_number": call.from_number,
                "summary": call.summary,
            }
            events.append((hint.user_id, missed, alert))
        await session.commit()
    for user_id, missed, alert in events:
        await notify(user_id, missed, push=True, collapse_key=missed["call_id"])
        if alert is not None:
            await notify(user_id, alert, push=True, collapse_key="forwarding")
    return len(events)


async def unreached_loop(interval: float = 15.0) -> None:
    import asyncio

    while True:
        try:
            await sweep_unreached()
        except Exception:
            logger.exception("Unreached-call sweep failed")
        await asyncio.sleep(interval)
