"""Sign-in, profile, devices, plan and the WebSocket ticket."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete, func, select

from app import ratelimit
from app.config import get_settings
from app.db import utcnow
from app.deps import CurrentUser, Session
from app.entitlements import entitlement_for
from app.models import (
    SupportReport,
    AssistantSettings,
    Call,
    CallAction,
    ChatMessage,
    ContactEntry,
    Device,
    Line,
    OutboundTask,
    Purchase,
    RefreshToken,
    Rule,
    ScreeningHint,
    TranscriptSegment,
    User,
)
from app.phone import normalize
from app.schemas import (
    SupportReportIn,
    SupportReportOut,
    DeviceIn,
    DevLogin,
    EntitlementOut,
    FirebaseLogin,
    MeUpdate,
    PublicConfig,
    RefreshIn,
    StatsOut,
    TokensOut,
    UserOut,
)
from app.security import AuthError, create_access_token, create_refresh_token_id, create_ws_ticket, verify_firebase_phone_token
from app.services.lines import release_line
from app.storage import delete_recording
from app.voice.services import missing_keys

router = APIRouter()


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        phone=user.phone_e164,
        name=user.name,
        language=user.language,
        plan=user.plan,
        onboarding_completed=user.onboarding_completed_at is not None,
    )


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {"ok": True}


@router.get("/v1/config", response_model=PublicConfig)
async def public_config() -> PublicConfig:
    s = get_settings()
    modes = []
    if s.firebase_project_id:
        modes.append("firebase")
    if s.dev_auth_enabled and s.is_dev:
        modes.append("dev")
    if s.beta_login_enabled:
        modes.append("beta")
    missing = missing_keys()
    return PublicConfig(
        auth_modes=modes,
        dev_code_hint=s.dev_auth_code if "dev" in modes else None,
        telephony_provider=s.telephony_provider,
        voice_ready=not missing,
        missing_keys=missing,
        play_products=s.play_pro_product_ids,
        support_email=s.support_email,
    )


def _token_key(refresh_token: str) -> str:
    """Refresh tokens are stored hashed, so a copy of the database can't be used to sign in."""
    return hashlib.sha256(refresh_token.encode()).hexdigest()


async def _issue(session: Session, phone: str) -> TokensOut:
    s = get_settings()
    user = await session.scalar(select(User).where(User.phone_e164 == phone))
    is_new = user is None
    if user is None:
        user = User(phone_e164=phone, trial_ends_at=utcnow() + timedelta(days=s.trial_days))
        session.add(user)
        await session.flush()
        session.add(AssistantSettings(user_id=user.id))
    refresh_id = create_refresh_token_id()
    session.add(RefreshToken(id=_token_key(refresh_id), user_id=user.id, expires_at=utcnow() + timedelta(days=s.refresh_token_ttl_days)))
    await session.commit()
    return TokensOut(
        access_token=create_access_token(user.id),
        refresh_token=refresh_id,
        expires_in=s.access_token_ttl_minutes * 60,
        user=user_out(user),
        is_new_user=is_new,
    )


@router.post("/v1/auth/firebase", response_model=TokensOut)
async def login_firebase(body: FirebaseLogin, session: Session, request: Request) -> TokensOut:
    ratelimit.check(f"login-ip:{ratelimit.client_ip(request)}", limit=30, window_seconds=900)
    try:
        phone = await verify_firebase_phone_token(body.id_token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    normalized = normalize(phone)
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That phone number isn't valid")
    return await _issue(session, normalized)


@router.post("/v1/auth/dev", response_model=TokensOut)
async def login_dev(body: DevLogin, session: Session, request: Request) -> TokensOut:
    """Code login without SMS: any number in development, allowlisted beta numbers in production."""
    s = get_settings()
    phone = normalize(body.phone)
    # Code guessing: 5 tries per number and 20 per address every 15 minutes.
    ratelimit.check(f"login-ip:{ratelimit.client_ip(request)}", limit=20, window_seconds=900)
    ratelimit.check(f"login-phone:{phone or body.phone}", limit=5, window_seconds=900)
    dev_ok = s.dev_auth_enabled and s.is_dev
    beta_ok = s.beta_login_enabled and phone in s.beta_numbers
    if not (dev_ok or beta_ok):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This number isn't in the beta yet")
    if not phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid mobile number")
    expected = s.dev_auth_code if dev_ok else s.beta_login_code
    if not hmac.compare_digest(body.code, expected or ""):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code isn't right")
    return await _issue(session, phone)


@router.post("/v1/auth/refresh", response_model=TokensOut)
async def refresh(body: RefreshIn, session: Session, request: Request) -> TokensOut:
    ratelimit.check(f"refresh-ip:{ratelimit.client_ip(request)}", limit=60, window_seconds=900)
    token = await session.get(RefreshToken, _token_key(body.refresh_token))
    if token is not None and token.revoked:
        # A used token came back: someone copied it. Sign this account out everywhere.
        await session.execute(RefreshToken.__table__.update().where(RefreshToken.user_id == token.user_id).values(revoked=True))
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.")
    expires = token.expires_at.replace(tzinfo=UTC) if token and token.expires_at.tzinfo is None else (token.expires_at if token else None)
    if token is None or expires is None or expires < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.")
    token.revoked = True  # rotate on every use
    user = await session.get(User, token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return await _issue(session, user.phone_e164)


@router.post("/v1/auth/logout", status_code=204)
async def logout(body: RefreshIn, session: Session, user: CurrentUser) -> None:
    token = await session.get(RefreshToken, _token_key(body.refresh_token))
    if token and token.user_id == user.id:
        token.revoked = True
    await session.execute(delete(Device).where(Device.user_id == user.id))
    await session.commit()


@router.get("/v1/me", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.patch("/v1/me", response_model=UserOut)
async def update_me(body: MeUpdate, session: Session, user: CurrentUser) -> UserOut:
    if body.name is not None:
        user.name = body.name.strip() or None
    if body.language is not None:
        user.language = body.language
    if body.onboarding_completed:
        user.onboarding_completed_at = user.onboarding_completed_at or utcnow()
    await session.commit()
    return user_out(user)


@router.delete("/v1/me", status_code=204)
async def delete_me(session: Session, user: CurrentUser) -> None:
    """Deletes the account and everything attached to it. The app removes call forwarding first."""
    lines = (await session.scalars(select(Line).where(Line.user_id == user.id))).all()
    for line in lines:
        await release_line(session, line)
    for key in (await session.scalars(select(Call.recording_key).where(Call.user_id == user.id, Call.recording_key.is_not(None)))).all():
        await delete_recording(key)
    # Foreign keys cascade these too; deleting explicitly keeps the promise on any database.
    call_ids = select(Call.id).where(Call.user_id == user.id)
    await session.execute(delete(TranscriptSegment).where(TranscriptSegment.call_id.in_(call_ids)))
    await session.execute(delete(CallAction).where(CallAction.user_id == user.id))
    for model in (Call, ChatMessage, OutboundTask, Rule, ContactEntry, ScreeningHint, SupportReport, Device, RefreshToken, Purchase, Line, AssistantSettings):
        await session.execute(delete(model).where(model.user_id == user.id))
    await session.flush()
    await session.delete(user)
    await session.commit()


@router.post("/v1/devices", status_code=204)
async def register_device(body: DeviceIn, session: Session, user: CurrentUser) -> None:
    device = await session.scalar(select(Device).where(Device.fcm_token == body.fcm_token))
    if device is None:
        device = Device(user_id=user.id, fcm_token=body.fcm_token)
        session.add(device)
    device.user_id = user.id
    device.platform = body.platform
    if body.live_activity_start_token:
        device.live_activity_start_token = body.live_activity_start_token
    device.app_version = body.app_version
    device.os_version = body.os_version
    await session.commit()


@router.get("/v1/me/entitlement", response_model=EntitlementOut)
async def get_entitlement(session: Session, user: CurrentUser) -> EntitlementOut:
    ent = await entitlement_for(session, user)
    return EntitlementOut(**ent.__dict__)


@router.get("/v1/me/stats", response_model=StatsOut)
async def stats(session: Session, user: CurrentUser) -> StatsOut:
    base = select(func.count(Call.id)).where(Call.user_id == user.id, Call.mode.in_(("screen", "message_only")))
    handled = int(await session.scalar(base) or 0)
    spam = int(await session.scalar(base.where(Call.is_spam.is_(True))) or 0)
    week = int(await session.scalar(base.where(Call.started_at >= utcnow() - timedelta(days=7))) or 0)
    seconds = int(await session.scalar(select(func.coalesce(func.sum(Call.duration_seconds), 0)).where(Call.user_id == user.id)) or 0)
    return StatsOut(calls_handled=handled, spam_blocked=spam, minutes_saved=max(handled * 2, seconds // 60), calls_this_week=week)


@router.post("/v1/stream/ticket")
async def stream_ticket(user: CurrentUser) -> dict:
    return {"ticket": create_ws_ticket(user.id)}


@router.post("/v1/support/report", response_model=SupportReportOut, status_code=201)
async def report_problem(body: SupportReportIn, session: Session, user: CurrentUser) -> SupportReportOut:
    """"Report a problem": the user's note plus the setup details we'd otherwise have to ask for."""
    ratelimit.check(f"support:{user.id}", 5, 3600)
    line = await session.scalar(
        select(Line).where(Line.user_id == user.id, Line.status != "released").order_by(Line.created_at.desc())
    )
    ent = await entitlement_for(session, user)
    last_call = await session.scalar(select(func.max(Call.started_at)).where(Call.user_id == user.id))
    server = {
        "line_status": line.status if line else "none",
        "carrier": line.carrier if line else None,
        "sim_count": line.sim_count if line else None,
        "ring_seconds": line.ring_seconds if line else None,
        "last_forwarded_at": line.last_forwarded_at.isoformat() if line and line.last_forwarded_at else None,
        "missed_streak": line.missed_streak if line else None,
        "plan": ent.level,
        "last_call_at": last_call.isoformat() if last_call else None,
    }
    app_side = {str(k)[:40]: (v[:200] if isinstance(v, str) else v) for k, v in body.diagnostics.items()}
    report = SupportReport(user_id=user.id, message=body.message.strip(), diagnostics={"app": app_side, "server": server})
    session.add(report)
    await session.commit()
    return SupportReportOut(id=report.id, created_at=report.created_at)
