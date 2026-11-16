"""Tokens: our own short-lived JWT access tokens plus rotating refresh tokens stored in the DB.

Sign-in itself is proven by a Firebase phone-auth ID token (production) or a fixed
code (DEV_AUTH_ENABLED, local development only).
"""

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from starlette.concurrency import run_in_threadpool

from app.config import get_settings

ALGORITHM = "HS256"


class AuthError(Exception):
    pass


def create_access_token(user_id: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": user_id, "typ": "access", "iat": now, "exp": now + timedelta(minutes=s.access_token_ttl_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token_id() -> str:
    return secrets.token_urlsafe(32)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired token") from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise AuthError("Invalid token type")
    return str(payload["sub"])


def create_ws_ticket(user_id: str, ttl_seconds: int = 60) -> str:
    """Short-lived token for opening the WebSocket (query strings end up in logs)."""
    now = datetime.now(UTC)
    payload = {"sub": user_id, "typ": "ws", "exp": now + timedelta(seconds=ttl_seconds)}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_ws_ticket(token: str) -> str:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired ticket") from exc
    if payload.get("typ") not in ("ws", "access"):
        raise AuthError("Invalid ticket")
    return str(payload["sub"])


async def verify_firebase_phone_token(id_token: str) -> str:
    """Return the verified E.164 phone number from a Firebase Auth ID token."""
    project_id = get_settings().firebase_project_id
    if not project_id:
        raise AuthError("Firebase sign-in is not configured on this server")

    def _verify() -> dict:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        return google_id_token.verify_firebase_token(id_token, google_requests.Request(), audience=project_id)

    try:
        claims = await run_in_threadpool(_verify)
    except Exception as exc:  # google-auth raises ValueError / TransportError
        raise AuthError("Could not verify the sign-in token") from exc
    phone = claims.get("phone_number")
    if not phone:
        raise AuthError("The sign-in token has no phone number")
    return str(phone)
