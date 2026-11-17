"""Assistant number, forwarding, assistant settings, rules, contacts and screening."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.db import utcnow
from app.deps import CurrentUser, Session
from app.forwarding import DEACTIVATE_ALL_CODE, DEACTIVATE_CODE, activation_codes, carrier_note, clamp_ring_seconds
from app.models import AssistantSettings, ContactEntry, Line, NumberPoolEntry, Rule, ScreeningHint
from app.packs import CATEGORIES, PACKS
from app.phone import normalize, pretty
from app.ai.prompts import LANGUAGE_NAMES as LANGUAGE_OPTIONS
from app.schemas import (
    AssistantOut,
    AssistantUpdate,
    ContactsSync,
    ForwardingCodeOut,
    LineIn,
    LineOut,
    LineUpdate,
    OptionsOut,
    PackOut,
    RuleIn,
    RuleOut,
    ScreeningHintIn,
    VoiceOut,
)
from app.services.lines import NoNumbersAvailable, TelephonyNotConfigured, allocate_number, release_line, start_verification
from app.voice.services import SARVAM_VOICES

router = APIRouter(prefix="/v1")


def line_out(line: Line) -> LineOut:
    return LineOut(
        id=line.id,
        phone=line.phone_e164,
        assistant_number=line.assistant_number,
        assistant_number_display=pretty(line.assistant_number),
        status=line.status,
        carrier=line.carrier,
        carrier_note=carrier_note(line.carrier),
        ring_seconds=line.ring_seconds,
        verified_at=line.verified_at,
        last_forwarded_at=line.last_forwarded_at,
        activation_codes=[ForwardingCodeOut(**c.__dict__) for c in activation_codes(line.assistant_number, line.ring_seconds)],
        deactivation_code=DEACTIVATE_CODE,
        deactivation_all_code=DEACTIVATE_ALL_CODE,
    )


async def _current_line(session: Session, user_id: str) -> Line | None:
    return await session.scalar(select(Line).where(Line.user_id == user_id, Line.status != "released").order_by(Line.created_at.desc()))


@router.post("/lines", response_model=LineOut)
async def create_line(body: LineIn, session: Session, user: CurrentUser) -> LineOut:
    existing = await _current_line(session, user.id)
    if existing:
        return line_out(existing)
    phone = normalize(body.phone) if body.phone else user.phone_e164
    if not phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid mobile number")
    if phone != user.phone_e164:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use the number you signed in with. It has to be the SIM in this phone.")
    try:
        entry = await allocate_number(session, user.id)
    except NoNumbersAvailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "We're setting up more assistant numbers. Try again in a few minutes.") from exc
    line = Line(
        user_id=user.id,
        phone_e164=phone,
        carrier=body.carrier,
        sim_count=body.sim_count,
        assistant_number=entry.number,
        ring_seconds=clamp_ring_seconds(body.ring_seconds),
    )
    session.add(line)
    await session.commit()
    return line_out(line)


@router.get("/lines/current", response_model=LineOut)
async def get_line(session: Session, user: CurrentUser) -> LineOut:
    line = await _current_line(session, user.id)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No assistant number yet")
    return line_out(line)


@router.patch("/lines/{line_id}", response_model=LineOut)
async def update_line(line_id: str, body: LineUpdate, session: Session, user: CurrentUser) -> LineOut:
    line = await session.get(Line, line_id)
    if line is None or line.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if body.ring_seconds is not None:
        line.ring_seconds = clamp_ring_seconds(body.ring_seconds)
    if body.carrier is not None:
        line.carrier = body.carrier
    if body.sim_count is not None:
        line.sim_count = body.sim_count
    await session.commit()
    return line_out(line)


@router.post("/lines/{line_id}/verify", status_code=202)
async def verify_line(line_id: str, session: Session, user: CurrentUser) -> dict:
    line = await session.get(Line, line_id)
    if line is None or line.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    try:
        await start_verification(session, line)
    except TelephonyNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Test calls aren't available yet on this server") from exc
    return {"status": "calling", "expires_in": 120}


@router.delete("/lines/{line_id}", status_code=204)
async def delete_line(line_id: str, session: Session, user: CurrentUser) -> None:
    line = await session.get(Line, line_id)
    if line is None or line.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await release_line(session, line)
    await session.commit()


def assistant_out(prefs: AssistantSettings) -> AssistantOut:
    return AssistantOut(
        assistant_name=prefs.assistant_name,
        voice=prefs.voice,
        languages=list(prefs.languages or []),
        greeting=prefs.greeting,
        instructions=prefs.instructions or "",
        pack_ids=list(prefs.pack_ids or []),
        screening_mode=prefs.screening_mode,
        screen_contacts=prefs.screen_contacts,
        snooze_until=prefs.snooze_until,
        record_calls=prefs.record_calls,
        retention_days=prefs.retention_days,
        urgent_passthrough=prefs.urgent_passthrough,
        delivery_note=prefs.delivery_note,
    )


async def _prefs(session: Session, user_id: str) -> AssistantSettings:
    prefs = await session.get(AssistantSettings, user_id)
    if prefs is None:
        prefs = AssistantSettings(user_id=user_id)
        session.add(prefs)
        await session.flush()
    return prefs


@router.get("/assistant", response_model=AssistantOut)
async def get_assistant(session: Session, user: CurrentUser) -> AssistantOut:
    prefs = await _prefs(session, user.id)
    await session.commit()
    return assistant_out(prefs)


@router.patch("/assistant", response_model=AssistantOut)
async def update_assistant(body: AssistantUpdate, session: Session, user: CurrentUser) -> AssistantOut:
    prefs = await _prefs(session, user.id)
    data = body.model_dump(exclude_unset=True)
    snooze = data.pop("snooze_minutes", None)
    if "voice" in data and data["voice"] not in SARVAM_VOICES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown voice")
    if "pack_ids" in data:
        known = {p.id for p in PACKS}
        data["pack_ids"] = [p for p in data["pack_ids"] if p in known]
    if "languages" in data:
        data["languages"] = [code for code in data["languages"] if code in LANGUAGE_OPTIONS][:3] or ["en-IN"]
    for key, value in data.items():
        setattr(prefs, key, value)
    if snooze is not None:
        prefs.snooze_until = utcnow() + timedelta(minutes=snooze) if snooze else None
    await session.commit()
    return assistant_out(prefs)


@router.get("/assistant/options", response_model=OptionsOut)
async def options() -> OptionsOut:
    return OptionsOut(
        packs=[PackOut(**p.__dict__) for p in PACKS],
        categories=CATEGORIES,
        voices=[VoiceOut(id=k, label=v) for k, v in SARVAM_VOICES.items()],
        languages=LANGUAGE_OPTIONS,
    )


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(session: Session, user: CurrentUser) -> list[RuleOut]:
    rules = (await session.scalars(select(Rule).where(Rule.user_id == user.id).order_by(Rule.created_at))).all()
    return [RuleOut(id=r.id, match_type=r.match_type, match_value=r.match_value, action=r.action, note=r.note) for r in rules]


@router.put("/rules", response_model=list[RuleOut])
async def replace_rules(body: list[RuleIn], session: Session, user: CurrentUser) -> list[RuleOut]:
    await session.execute(delete(Rule).where(Rule.user_id == user.id))
    out = []
    for item in body[:100]:
        value = item.match_value
        if item.match_type == "number":
            value = normalize(value) or ""
            if not value:
                continue
        elif value not in CATEGORIES:
            continue
        rule = Rule(user_id=user.id, match_type=item.match_type, match_value=value, action=item.action, note=item.note)
        session.add(rule)
        await session.flush()
        out.append(RuleOut(id=rule.id, match_type=rule.match_type, match_value=rule.match_value, action=rule.action, note=rule.note))
    await session.commit()
    return out


@router.post("/contacts/sync")
async def sync_contacts(body: ContactsSync, session: Session, user: CurrentUser) -> dict:
    if body.replace:
        await session.execute(delete(ContactEntry).where(ContactEntry.user_id == user.id))
    seen: set[str] = set()
    for contact in body.contacts:
        for raw in contact.numbers[:5]:
            number = normalize(raw)
            if not number or number in seen:
                continue
            seen.add(number)
            session.add(ContactEntry(user_id=user.id, number_e164=number, name=contact.name[:120]))
    await session.commit()
    return {"saved": len(seen)}


@router.post("/screening/hints", status_code=204)
async def screening_hint(body: ScreeningHintIn, session: Session, user: CurrentUser) -> None:
    number = normalize(body.caller_number)
    if not number:
        return
    session.add(ScreeningHint(user_id=user.id, caller_number=number, decision=body.decision))
    await session.commit()


@router.get("/screening/policy")
async def screening_policy(session: Session, user: CurrentUser) -> dict:
    """Everything the phone needs to screen calls offline, cached on the device."""
    prefs = await _prefs(session, user.id)
    line = await _current_line(session, user.id)
    rules = (await session.scalars(select(Rule).where(Rule.user_id == user.id, Rule.match_type == "number"))).all()
    system_numbers = (await session.scalars(select(NumberPoolEntry.number).where(NumberPoolEntry.user_id == user.id))).all()
    await session.commit()
    return {
        "screening_mode": prefs.screening_mode,
        "screen_contacts": prefs.screen_contacts,
        "snooze_until": prefs.snooze_until.isoformat() if prefs.snooze_until else None,
        "line_status": line.status if line else "none",
        "assistant_number": line.assistant_number if line else None,
        "always_ring": sorted({r.match_value for r in rules if r.action in ("ring_me", "connect")} | set(system_numbers)),
        "always_screen": sorted({r.match_value for r in rules if r.action in ("decline", "handle")}),
    }
