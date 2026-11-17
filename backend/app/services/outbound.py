"""Calls the assistant makes for the user ("call the clinic tomorrow at 10 and book a checkup")."""

import asyncio
from datetime import datetime, timedelta

from loguru import logger
import phonenumbers
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import sessionmaker, utcnow
from app.events import bus, user_topic
from app.models import Call, Line, NumberPoolEntry, OutboundTask
from app.telephony.registry import get_provider


# Number types the assistant may call: no premium-rate, shared-cost or other paid services.
_CALLABLE_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE,
    phonenumbers.PhoneNumberType.FIXED_LINE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    phonenumbers.PhoneNumberType.TOLL_FREE,
}


async def outbound_problem(session: AsyncSession, user_id: str, e164: str) -> str | None:
    """Why the assistant can't call this number for this user now, or None if it can.

    Guards against toll fraud and misuse: only ordinary numbers in allowed countries, and a
    daily and pending cap per user.
    """
    s = get_settings()
    try:
        parsed = phonenumbers.parse(e164, None)
    except phonenumbers.NumberParseException:
        return "That phone number isn't valid."
    if phonenumbers.region_code_for_number(parsed) not in s.outbound_countries:
        return "Your assistant can only call Indian numbers for now."
    if phonenumbers.number_type(parsed) not in _CALLABLE_TYPES:
        return "Your assistant can't call premium or special-rate numbers."
    since = utcnow() - timedelta(hours=24)
    today = await session.scalar(select(func.count()).select_from(OutboundTask).where(OutboundTask.user_id == user_id, OutboundTask.created_at >= since))
    if (today or 0) >= s.outbound_daily_limit:
        return f"Your assistant can place up to {s.outbound_daily_limit} calls a day. Try again tomorrow."
    pending = await session.scalar(
        select(func.count()).select_from(OutboundTask).where(OutboundTask.user_id == user_id, OutboundTask.state.in_(("scheduled", "dialing")))
    )
    if (pending or 0) >= s.outbound_pending_limit:
        return f"You already have {s.outbound_pending_limit} calls waiting. Cancel one or wait for them to finish."
    return None

RETRY_DELAY = timedelta(minutes=5)
MAX_ATTEMPTS = 3


async def dial(task_id: str) -> None:
    async with sessionmaker()() as session:
        # Atomic claim: only one instance moves a task out of "scheduled", so it is dialed once.
        claimed = await session.execute(
            update(OutboundTask).where(OutboundTask.id == task_id, OutboundTask.state == "scheduled").values(state="dialing")
        )
        await session.commit()
        if claimed.rowcount != 1:
            return
        task = await session.get(OutboundTask, task_id)
        if task is None:
            return
        line = await session.scalar(select(Line).where(Line.user_id == task.user_id, Line.status != "released").order_by(Line.created_at.desc()))
        if line is None:
            task.state = "failed"
            task.result_summary = "Set up your assistant number first."
            await session.commit()
            return
        entry = await session.get(NumberPoolEntry, line.assistant_number)
        provider = get_provider(entry.provider if entry else None)
        call = Call(
            user_id=task.user_id,
            line_id=line.id,
            direction="outbound",
            mode="outbound",
            provider=provider.name,
            from_number=line.assistant_number,
            to_number=task.to_number,
            caller_known_name=task.to_name,
            outbound_task_id=task.id,
            state="ringing",
        )
        session.add(call)
        await session.flush()  # assigns call.id
        task.state = "dialing"
        task.attempts += 1
        task.call_id = call.id
        await session.commit()
        call_id, user_id = call.id, task.user_id
    try:
        provider_call_id = await provider.place_call(to_number=task.to_number, from_number=line.assistant_number, call_id=call_id, purpose="outbound")
    except Exception as exc:
        logger.warning(f"Outbound call failed to start: {exc}")
        async with sessionmaker()() as session:
            task = await session.get(OutboundTask, task_id)
            call = await session.get(Call, call_id)
            if call:
                call.state = "failed"
                call.end_reason = "dial_failed"
            if task:
                if task.attempts < MAX_ATTEMPTS:
                    task.state = "scheduled"
                    task.scheduled_at = utcnow() + RETRY_DELAY
                else:
                    task.state = "failed"
                    task.result_summary = "Couldn't place the call."
            await session.commit()
        await bus.publish(user_topic(user_id), {"type": "outbound.updated", "task_id": task_id})
        return
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call and provider_call_id:
            call.provider_call_id = provider_call_id
            await session.commit()
    await bus.publish(user_topic(user_id), {"type": "outbound.updated", "task_id": task_id, "call_id": call_id})


async def due_task_ids(now: datetime) -> list[str]:
    async with sessionmaker()() as session:
        rows = await session.scalars(select(OutboundTask.id).where(OutboundTask.state == "scheduled", OutboundTask.scheduled_at <= now).limit(20))
        return list(rows)


async def scheduler_loop(interval: float = 10.0) -> None:
    while True:
        try:
            for task_id in await due_task_ids(utcnow()):
                asyncio.create_task(dial(task_id))
        except Exception:
            logger.exception("Outbound scheduler tick failed")
        await asyncio.sleep(interval)


async def complete_from_summary(call_id: str) -> None:
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None or not call.outbound_task_id:
            return
        task = await session.get(OutboundTask, call.outbound_task_id)
        if task is None:
            return
        task.state = "done"
        task.result_summary = call.summary
        await session.commit()
        user_id = task.user_id
    await bus.publish(user_topic(user_id), {"type": "outbound.updated", "task_id": task.id, "call_id": call_id})
