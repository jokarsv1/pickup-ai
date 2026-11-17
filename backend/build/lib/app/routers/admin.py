"""Operator endpoints (X-Admin-Token): load rented numbers into the pool, check health."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.deps import Session, require_admin
from app.models import Call, NumberPoolEntry, User
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
