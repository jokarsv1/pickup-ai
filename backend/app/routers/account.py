"""Sign-in, profile, devices, plan and the WebSocket ticket."""

import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.db import utcnow
from app.deps import CurrentUser, Session
from app.entitlements import entitlement_for
from app.models import AssistantSettings, Call, Device, Line, RefreshToken, User
from app.phone import normalize
from app.schemas import (
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
    session.add(RefreshToken(id=refresh_id, user_id=user.id, expires_at=utcnow() + timedelta(days=s.refresh_token_ttl_days)))
    await session.commit()
    return TokensOut(
        access_token=create_access_token(user.id),
        refresh_token=refresh_id,
        expires_in=s.access_token_ttl_minutes * 60,
        user=user_out(user),
        is_new_user=is_new,
    )


@router.post("/v1/auth/firebase", response_model=TokensOut)
async def login_firebase(body: FirebaseLogin, session: Session) -> TokensOut:
    try:
        phone = await verify_firebase_phone_token(body.id_token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    normalized = normalize(phone)
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That phone number isn't valid")
    return await _issue(session, normalized)


@router.post("/v1/auth/dev", response_model=TokensOut)
async def login_dev(body: DevLogin, session: Session) -> TokensOut:
    """Code login without SMS: any number in development, allowlisted beta numbers in production."""
    s = get_settings()
    phone = normalize(body.phone)
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
async def refresh(body: RefreshIn, session: Session) -> TokensOut:
    token = await session.get(RefreshToken, body.refresh_token)
    expires = token.expires_at.replace(tzinfo=UTC) if token and token.expires_at.tzinfo is None else (token.expires_at if token else None)
    if token is None or token.revoked or expires is None or expires < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.")
    token.revoked = True  # rotate on every use
    user = await session.get(User, token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return await _issue(session, user.phone_e164)


@router.post("/v1/auth/logout", status_code=204)
async def logout(body: RefreshIn, session: Session, user: CurrentUser) -> None:
    token = await session.get(RefreshToken, body.refresh_token)
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
