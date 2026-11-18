"""Plans: a 7-day full trial, then Free (limited calls per month) or Pro.

Your own calls are never held back: every plan keeps live transcripts, quick replies, joining a
call, summaries, transcripts and recordings. Plans differ only in how many calls the assistant
answers each month and in AI outbound calls. (Equal AI's users were angriest about paying to hear
their own calls.)
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Call, User


@dataclass
class Entitlement:
    level: str  # pro | trial | free | limited
    live_controls: bool  # live transcript, quick replies, take over
    outbound_calls: bool
    recordings: bool
    calls_left_this_month: int | None
    trial_ends_at: datetime | None
    plan_expires_at: datetime | None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def calls_this_month(session: AsyncSession, user_id: str) -> int:
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q = select(func.count(Call.id)).where(Call.user_id == user_id, Call.started_at >= start, Call.direction == "inbound", Call.mode == "screen")
    return int((await session.scalar(q)) or 0)


async def entitlement_for(session: AsyncSession, user: User) -> Entitlement:
    now = datetime.now(UTC)
    plan_expires = _aware(user.plan_expires_at)
    trial_ends = _aware(user.trial_ends_at)
    if user.plan == "pro" and (plan_expires is None or plan_expires > now):
        return Entitlement("pro", True, True, True, None, trial_ends, plan_expires)
    if trial_ends and trial_ends > now:
        return Entitlement("trial", True, True, True, None, trial_ends, plan_expires)
    used = await calls_this_month(session, user.id)
    left = max(0, get_settings().free_calls_per_month - used)
    level = "free" if left > 0 else "limited"
    return Entitlement(level, True, False, True, left, trial_ends, plan_expires)
