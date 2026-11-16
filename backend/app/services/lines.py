"""Assistant numbers: assignment from the pool, release with quarantine, forwarding verification."""

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import Line, NumberPoolEntry
from app.telephony.registry import get_provider

QUARANTINE = timedelta(days=30)
VERIFY_WINDOW = timedelta(minutes=2)


class NoNumbersAvailable(Exception):
    pass


class TelephonyNotConfigured(Exception):
    pass


async def allocate_number(session: AsyncSession, user_id: str) -> NumberPoolEntry:
    existing = await session.scalar(select(NumberPoolEntry).where(NumberPoolEntry.user_id == user_id, NumberPoolEntry.state == "assigned"))
    if existing:
        return existing
    now = utcnow()
    q = (
        select(NumberPoolEntry)
        .where(or_(NumberPoolEntry.state == "free", (NumberPoolEntry.state == "quarantine") & (NumberPoolEntry.quarantine_until < now)))
        .order_by(NumberPoolEntry.number)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    entry = await session.scalar(q)
    if entry is None:
        raise NoNumbersAvailable()
    entry.state = "assigned"
    entry.user_id = user_id
    entry.assigned_at = now
    entry.quarantine_until = None
    return entry


async def release_line(session: AsyncSession, line: Line) -> None:
    """Numbers rest for 30 days before reuse, so a stranger never gets the old owner's forwarded calls."""
    line.status = "released"
    entry = await session.get(NumberPoolEntry, line.assistant_number)
    if entry is not None:
        entry.state = "quarantine"
        entry.user_id = None
        entry.quarantine_until = utcnow() + QUARANTINE


async def start_verification(session: AsyncSession, line: Line) -> None:
    """Ring the user's phone from their assistant number. The app declines it; if forwarding works,
    the carrier sends it straight back to the assistant number and we mark the line verified."""
    entry = await session.get(NumberPoolEntry, line.assistant_number)
    provider = get_provider(entry.provider if entry else None)
    if not provider.configured:
        raise TelephonyNotConfigured()
    line.verification_pending_until = utcnow() + VERIFY_WINDOW
    await session.commit()
    await provider.place_call(to_number=line.phone_e164, from_number=line.assistant_number, call_id=f"verify-{line.id}", purpose="verify")
