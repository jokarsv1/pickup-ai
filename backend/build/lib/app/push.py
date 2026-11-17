"""Push notifications through Firebase Cloud Messaging HTTP v1.

All messages are data-only and high priority: the app builds the notification itself, so
it can show the live transcript, smart replies and the Join button, and update one
notification in place instead of stacking new ones.
"""

import asyncio
import json
import time
from typing import Any, Protocol

import httpx
from loguru import logger
from sqlalchemy import delete, select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import sessionmaker
from app.models import Device

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushSender(Protocol):
    async def send_to_user(self, user_id: str, data: dict[str, Any], *, collapse_key: str | None = None) -> int: ...


class NoopPush:
    """Used when FCM is not configured. The WebSocket still delivers events to an open app."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    async def send_to_user(self, user_id: str, data: dict[str, Any], *, collapse_key: str | None = None) -> int:
        self.sent.append((user_id, data))
        return 0


class FcmPush:
    def __init__(self, service_account_info: dict[str, Any]) -> None:
        from google.oauth2 import service_account

        self._project_id = service_account_info["project_id"]
        self._credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=[FCM_SCOPE])
        self._client = httpx.AsyncClient(timeout=10)
        self._lock = asyncio.Lock()

    async def _token(self) -> str:
        async with self._lock:
            if not self._credentials.valid:
                from google.auth.transport.requests import Request

                await run_in_threadpool(self._credentials.refresh, Request())
            return self._credentials.token

    async def send_to_user(self, user_id: str, data: dict[str, Any], *, collapse_key: str | None = None) -> int:
        async with sessionmaker()() as session:
            tokens = (await session.scalars(select(Device.fcm_token).where(Device.user_id == user_id))).all()
        if not tokens:
            return 0
        access_token = await self._token()
        url = f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
        payload_data = {k: v if isinstance(v, str) else json.dumps(v, default=str) for k, v in data.items()}
        sent = 0
        for token in tokens:
            android: dict[str, Any] = {"priority": "HIGH", "ttl": "120s"}
            if collapse_key:
                android["collapse_key"] = collapse_key
            body = {"message": {"token": token, "android": android, "data": payload_data}}
            resp = await self._client.post(url, json=body, headers={"Authorization": f"Bearer {access_token}"})
            if resp.status_code == 200:
                sent += 1
            elif resp.status_code == 404 or "UNREGISTERED" in resp.text:
                await self._forget(token)
            else:
                logger.warning(f"FCM send failed {resp.status_code}: {resp.text[:200]}")
        return sent

    async def _forget(self, token: str) -> None:
        async with sessionmaker()() as session:
            await session.execute(delete(Device).where(Device.fcm_token == token))
            await session.commit()


class Throttle:
    """At most one push per key per interval; the latest payload wins (sent on the trailing edge)."""

    def __init__(self, sender: PushSender, interval: float = 1.5) -> None:
        self._sender = sender
        self._interval = interval
        self._last: dict[str, float] = {}
        self._pending: dict[str, tuple[str, dict[str, Any], str | None]] = {}
        self._timers: dict[str, asyncio.Task] = {}

    async def send(self, key: str, user_id: str, data: dict[str, Any], collapse_key: str | None = None) -> None:
        now = time.monotonic()
        last = self._last.get(key, 0.0)
        if now - last >= self._interval and key not in self._timers:
            self._last[key] = now
            await self._sender.send_to_user(user_id, data, collapse_key=collapse_key)
            return
        self._pending[key] = (user_id, data, collapse_key)
        if key not in self._timers:
            delay = max(0.0, self._interval - (now - last))
            self._timers[key] = asyncio.create_task(self._flush_later(key, delay))

    async def _flush_later(self, key: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            pending = self._pending.pop(key, None)
            if pending:
                self._last[key] = time.monotonic()
                user_id, data, collapse_key = pending
                await self._sender.send_to_user(user_id, data, collapse_key=collapse_key)
        finally:
            self._timers.pop(key, None)


_push: PushSender | None = None


def get_push() -> PushSender:
    global _push
    if _push is None:
        s = get_settings()
        info: dict[str, Any] | None = None
        if s.fcm_service_account_json:
            info = json.loads(s.fcm_service_account_json)
        elif s.fcm_service_account_file:
            with open(s.fcm_service_account_file, encoding="utf-8") as fh:
                info = json.load(fh)
        _push = FcmPush(info) if info else NoopPush()
        if info is None:
            logger.info("FCM not configured: push notifications are off")
    return _push


def set_push(sender: PushSender) -> None:
    global _push
    _push = sender
