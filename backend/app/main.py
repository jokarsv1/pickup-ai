import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select

from app.config import get_settings
from app.db import create_all, sessionmaker, utcnow
from app.events import bus
from app.models import AssistantSettings, Call
from app.routers import account, admin, assistant_chat, calls, setup, telephony
from app.storage import delete_recording


async def retention_loop() -> None:
    """Delete recordings older than each user's retention setting, once an hour."""
    while True:
        try:
            async with sessionmaker()() as session:
                prefs = (await session.scalars(select(AssistantSettings))).all()
                for p in prefs:
                    cutoff = utcnow() - timedelta(days=p.retention_days)
                    old = (
                        await session.scalars(
                            select(Call).where(Call.user_id == p.user_id, Call.recording_key.is_not(None), Call.started_at < cutoff).limit(200)
                        )
                    ).all()
                    for call in old:
                        await delete_recording(call.recording_key or "")
                        call.recording_key = None
                await session.commit()
        except Exception:
            logger.exception("Retention sweep failed")
        await asyncio.sleep(3600)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    await create_all()
    await bus.start(s.redis_url)
    tasks: list[asyncio.Task] = []
    if s.env != "test":
        from app.services.outbound import scheduler_loop

        tasks = [asyncio.create_task(scheduler_loop()), asyncio.create_task(retention_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await bus.stop()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Pickup API", version="0.1.0", lifespan=lifespan)
    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["*"], allow_headers=["*"])
    for module in (account, setup, calls, assistant_chat, telephony, admin):
        app.include_router(module.router)
    return app


app = create_app()
