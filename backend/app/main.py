import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import create_all, sessionmaker, utcnow
from app.events import bus
from app.models import AssistantSettings, Call, ScreeningHint
from app import downloads, legal
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
                # Screening hints only matter for a few minutes: keep two days for support, no more.
                await session.execute(delete(ScreeningHint).where(ScreeningHint.created_at < utcnow() - timedelta(days=2)))
                await session.commit()
        except Exception:
            logger.exception("Retention sweep failed")
        await asyncio.sleep(3600)


def _guessable(code: str) -> bool:
    digits = [int(ch) for ch in code if ch.isdigit()]
    if len(set(code)) <= 2 or code in {"123123", "121212", "112233", "123321", "147258", "159753"}:
        return True
    steps = {b - a for a, b in zip(digits, digits[1:])}
    return len(digits) == len(code) and steps in ({1}, {-1})


async def _prewarm_voice_models() -> None:
    """Load the speech models once at startup. Otherwise the first call after a restart waits
    about a second (imports plus the voice-activity and turn-taking models) before its greeting."""

    def load() -> None:
        from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
        from pipecat.audio.vad.silero import SileroVADAnalyzer

        SileroVADAnalyzer()
        LocalSmartTurnAnalyzerV3()

    try:
        await asyncio.to_thread(load)
        logger.info("Voice models loaded")
    except Exception:
        logger.exception("Voice model warm-up failed")


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    if s.beta_login_enabled and _guessable(s.beta_login_code or ""):
        logger.warning("BETA_LOGIN_CODE is easy to guess. Set a random 6+ digit code: anyone who knows a beta number could sign in.")
    if s.env != "prod":
        await create_all()  # production runs "alembic upgrade head" (see Dockerfile)
    await bus.start(s.redis_url)
    tasks: list[asyncio.Task] = []
    if s.env != "test":
        from app.services.outbound import scheduler_loop

        from app.services.calls import unreached_loop
        from app.voice.session import warm_recent_greetings

        tasks = [
            asyncio.create_task(scheduler_loop()),
            asyncio.create_task(retention_loop()),
            asyncio.create_task(unreached_loop()),
            asyncio.create_task(_prewarm_voice_models()),
            asyncio.create_task(warm_recent_greetings()),
        ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await bus.stop()


def create_app() -> FastAPI:
    s = get_settings()
    # The API explorer (/docs) is for development; production doesn't advertise its endpoints.
    docs = {} if s.is_dev else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Pickup API", version="0.1.0", lifespan=lifespan, **docs)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if not s.is_dev:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["*"], allow_headers=["*"])
    for module in (account, setup, calls, assistant_chat, telephony, admin, legal, downloads):
        app.include_router(module.router)
    return app


app = create_app()
