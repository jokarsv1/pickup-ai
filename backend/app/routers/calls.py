"""Call history, live controls (say this, join, end), recordings, feedback and actions."""

import base64
import json

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import or_, select

from app.db import utcnow
from app.deps import CurrentUser, Session
from app.entitlements import entitlement_for
from app.events import bus, call_topic
from app.models import Call, CallAction, TranscriptSegment
from app.packs import CATEGORIES
from app.schemas import ActionOut, ActionUpdate, CallDetailOut, CallPage, CallSummaryOut, FeedbackIn, LiveActivityTokenIn, SayIn, TranscriptLine
from app.services.calls import display_title
from app.storage import delete_recording, recording_url_or_path

router = APIRouter(prefix="/v1/calls")
LIVE_STATES = ("ringing", "live", "taken_over")


def summary_out(call: Call) -> CallSummaryOut:
    return CallSummaryOut(
        id=call.id,
        direction=call.direction,
        mode=call.mode,
        state=call.state,
        title=display_title(call),
        caller_number=call.from_number if call.direction == "inbound" else call.to_number,
        caller_known_name=call.caller_known_name,
        caller_name=call.caller_name,
        caller_org=call.caller_org,
        category=call.category,
        category_label=CATEGORIES.get(call.category) if call.category else None,
        reason=call.reason,
        summary=call.summary,
        urgency=call.urgency,
        is_spam=call.is_spam,
        started_at=call.started_at,
        duration_seconds=call.duration_seconds,
        has_recording=bool(call.recording_key),
        unread=call.read_at is None and call.state not in LIVE_STATES,
    )


def _cursor_encode(call: Call) -> str:
    return base64.urlsafe_b64encode(json.dumps([call.started_at.isoformat(), call.id]).encode()).decode()


def _cursor_decode(cursor: str) -> tuple[str, str]:
    started, call_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return started, call_id


async def _own_call(session: Session, user_id: str, call_id: str) -> Call:
    call = await session.get(Call, call_id)
    if call is None or call.user_id != user_id or call.deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found")
    return call


@router.get("", response_model=CallPage)
async def list_calls(
    session: Session,
    user: CurrentUser,
    q: str | None = Query(None, max_length=80),
    category: str | None = None,
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=100),
) -> CallPage:
    # Calls still in progress show in the live banner (GET /calls/live), not in the history.
    stmt = select(Call).where(Call.user_id == user.id, Call.deleted.is_(False), Call.mode != "demo", Call.state.not_in(LIVE_STATES))
    if category:
        stmt = stmt.where(Call.category == category)
    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func

        stmt = stmt.where(
            or_(
                func.lower(func.coalesce(Call.caller_name, "")).like(like),
                func.lower(func.coalesce(Call.caller_org, "")).like(like),
                func.lower(func.coalesce(Call.caller_known_name, "")).like(like),
                func.lower(func.coalesce(Call.summary, "")).like(like),
                func.lower(func.coalesce(Call.reason, "")).like(like),
                func.coalesce(Call.from_number, "").like(f"%{q}%"),
            )
        )
    if cursor:
        try:
            started, call_id = _cursor_decode(cursor)
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad cursor") from exc
        from datetime import datetime

        started_dt = datetime.fromisoformat(started)
        stmt = stmt.where(or_(Call.started_at < started_dt, (Call.started_at == started_dt) & (Call.id < call_id)))
    rows = (await session.scalars(stmt.order_by(Call.started_at.desc(), Call.id.desc()).limit(limit + 1))).all()
    items = [summary_out(c) for c in rows[:limit]]
    next_cursor = _cursor_encode(rows[limit - 1]) if len(rows) > limit else None
    return CallPage(items=items, next_cursor=next_cursor)


@router.get("/live", response_model=list[CallSummaryOut])
async def live_calls(session: Session, user: CurrentUser) -> list[CallSummaryOut]:
    rows = (
        await session.scalars(select(Call).where(Call.user_id == user.id, Call.state.in_(LIVE_STATES)).order_by(Call.started_at.desc()))
    ).all()
    return [summary_out(c) for c in rows]


@router.get("/{call_id}", response_model=CallDetailOut)
async def get_call(call_id: str, session: Session, user: CurrentUser) -> CallDetailOut:
    call = await _own_call(session, user.id, call_id)
    segments = (await session.scalars(select(TranscriptSegment).where(TranscriptSegment.call_id == call_id).order_by(TranscriptSegment.seq))).all()
    actions = (await session.scalars(select(CallAction).where(CallAction.call_id == call_id))).all()
    if call.read_at is None and call.state not in LIVE_STATES:
        call.read_at = utcnow()
        await session.commit()
    base = summary_out(call).model_dump()
    return CallDetailOut(
        **base,
        suggested_replies=list(call.suggested_replies or []),
        transcript=[TranscriptLine(seq=s.seq, speaker=s.speaker, text=s.text, at=s.created_at) for s in segments],
        actions=[ActionOut(id=a.id, type=a.type, title=a.title, payload=a.payload or {}, status=a.status) for a in actions],
        rating=call.rating,
        end_reason=call.end_reason,
    )


@router.get("/{call_id}/recording")
async def get_recording(call_id: str, session: Session, user: CurrentUser):
    call = await _own_call(session, user.id, call_id)
    if not call.recording_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No recording for this call")
    url, path = await recording_url_or_path(call.recording_key)
    if url:
        return RedirectResponse(url)
    if path:
        return FileResponse(path, media_type="audio/wav", filename=f"{call_id}.wav")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Recording is no longer available")


async def _live_call(session: Session, user, call_id: str) -> Call:
    call = await _own_call(session, user.id, call_id)
    if call.state not in ("ringing", "live"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This call has already ended")
    ent = await entitlement_for(session, user)
    if not ent.live_controls:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Live controls are part of Pickup Pro")
    return call


@router.post("/{call_id}/say", status_code=202)
async def say(call_id: str, body: SayIn, session: Session, user: CurrentUser) -> dict:
    await _live_call(session, user, call_id)
    await bus.publish(call_topic(call_id), {"type": "say", "text": body.text.strip()})
    return {"status": "sent"}


@router.post("/{call_id}/takeover", status_code=202)
async def takeover(call_id: str, session: Session, user: CurrentUser) -> dict:
    await _live_call(session, user, call_id)
    await bus.publish(call_topic(call_id), {"type": "takeover"})
    return {"status": "connecting", "message": "Your phone will ring in a few seconds. Answer it to talk to the caller."}


@router.post("/{call_id}/end", status_code=202)
async def end(call_id: str, session: Session, user: CurrentUser) -> dict:
    call = await _own_call(session, user.id, call_id)
    if call.state not in LIVE_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, "This call has already ended")
    await bus.publish(call_topic(call_id), {"type": "end"})
    return {"status": "ending"}


@router.post("/{call_id}/feedback", status_code=204)
async def feedback(call_id: str, body: FeedbackIn, session: Session, user: CurrentUser) -> None:
    call = await _own_call(session, user.id, call_id)
    call.rating = body.rating
    call.feedback = body.comment
    await session.commit()


@router.post("/{call_id}/actions/{action_id}", response_model=ActionOut)
async def update_action(call_id: str, action_id: str, body: ActionUpdate, session: Session, user: CurrentUser) -> ActionOut:
    action = await session.get(CallAction, action_id)
    if action is None or action.user_id != user.id or action.call_id != call_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    action.status = body.status
    await session.commit()
    return ActionOut(id=action.id, type=action.type, title=action.title, payload=action.payload or {}, status=action.status)


@router.post("/{call_id}/read", status_code=204)
async def mark_read(call_id: str, session: Session, user: CurrentUser) -> None:
    call = await _own_call(session, user.id, call_id)
    call.read_at = call.read_at or utcnow()
    await session.commit()


@router.delete("/{call_id}", status_code=204)
async def delete_call(call_id: str, session: Session, user: CurrentUser) -> None:
    call = await _own_call(session, user.id, call_id)
    if call.recording_key:
        await delete_recording(call.recording_key)
        call.recording_key = None
    call.deleted = True
    call.summary = None
    call.reason = None
    await session.execute(TranscriptSegment.__table__.delete().where(TranscriptSegment.call_id == call_id))
    await session.commit()


@router.post("/{call_id}/live-activity", status_code=204)
async def live_activity_token(call_id: str, body: LiveActivityTokenIn, session: Session, user: CurrentUser) -> None:
    """The iPhone app reports the push token of the Live Activity it shows for this call."""
    call = await _own_call(session, user.id, call_id)
    call.live_activity_token = body.token
    await session.commit()
