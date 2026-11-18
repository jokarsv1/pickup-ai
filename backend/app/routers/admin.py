"""Operator endpoints (X-Admin-Token): load rented numbers into the pool, check health."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.deps import Session, require_admin
from app.models import Call, NumberPoolEntry, SupportReport, User
from app.phone import normalize
from app.schemas import NumberIn
from app.voice.services import missing_keys

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)], include_in_schema=False)


@router.post("/numbers")
async def add_numbers(body: list[NumberIn], session: Session) -> dict:
    added = []
    for item in body:
        number = normalize(item.number, item.region)
        if not number:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid number {item.number}")
        if await session.get(NumberPoolEntry, number) is None:
            session.add(NumberPoolEntry(number=number, provider=item.provider, region=item.region))
            added.append(number)
    await session.commit()
    return {"added": added}


@router.get("/numbers")
async def list_numbers(session: Session) -> list[dict]:
    rows = (await session.scalars(select(NumberPoolEntry).order_by(NumberPoolEntry.number))).all()
    return [{"number": r.number, "provider": r.provider, "state": r.state, "user_id": r.user_id} for r in rows]


@router.get("/health")
async def health(session: Session) -> dict:
    free = await session.scalar(select(func.count()).select_from(NumberPoolEntry).where(NumberPoolEntry.state == "free"))
    users = await session.scalar(select(func.count()).select_from(User))
    calls = await session.scalar(select(func.count()).select_from(Call))
    return {"free_numbers": free, "users": users, "calls": calls, "missing_keys": missing_keys()}


@router.get("/support")
async def list_support(session: Session, status_filter: str = "open", limit: int = 50) -> list[dict]:
    """Problems users reported from the app, newest first, with their setup details."""
    q = select(SupportReport, User).join(User, User.id == SupportReport.user_id).order_by(SupportReport.created_at.desc()).limit(min(limit, 200))
    if status_filter != "all":
        q = q.where(SupportReport.status == status_filter)
    rows = (await session.execute(q)).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "status": r.status,
            "user": {"id": u.id, "phone": u.phone_e164, "name": u.name},
            "message": r.message,
            "diagnostics": r.diagnostics,
        }
        for r, u in rows
    ]


@router.patch("/support/{report_id}")
async def update_support(report_id: str, session: Session, status_value: str = "closed") -> dict:
    report = await session.get(SupportReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if status_value not in ("open", "answered", "closed"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown status")
    report.status = status_value
    await session.commit()
    return {"id": report.id, "status": report.status}
