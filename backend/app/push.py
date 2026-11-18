"""Push notifications: Firebase Cloud Messaging (Android) and Apple Push Notification service (iPhone).

Android messages are data-only and high priority: the app builds the notification itself, so
it can show the live transcript, smart replies and the Join button, and update one
notification in place instead of stacking new ones. iPhones get visible alerts (iOS shows them
while the app is closed), collapsed per call so a call updates one notification.
"""

import asyncio
import json
import time
from typing import Any, Protocol

import httpx
import jwt
from loguru import logger
from sqlalchemy import delete, select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import sessionmaker
from app.models import Call, Device

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
            tokens = (await session.scalars(select(Device.fcm_token).where(Device.user_id == user_id, Device.platform != "ios"))).all()
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
        await forget_device(token)


async def forget_device(token: str) -> None:
    """Drop a device the push service says no longer exists."""
    async with sessionmaker()() as session:
        await session.execute(delete(Device).where(Device.fcm_token == token))
        await session.commit()


class ApnsPush:
    """Apple Push Notification service with token (.p8 key) authentication."""

    def __init__(self, key_p8: str, key_id: str, team_id: str, topic: str, sandbox: bool = False) -> None:
        self._key = key_p8.replace("\\n", "\n")
        self._key_id = key_id
        self._team_id = team_id
        self._topic = topic
        self._host = "https://api.sandbox.push.apple.com" if sandbox else "https://api.push.apple.com"
        self._client = httpx.AsyncClient(http2=True, timeout=10)
        self._jwt: str | None = None
        self._jwt_at = 0.0

    def _bearer(self) -> str:
        # Apple wants the token refreshed between 20 and 60 minutes.
        if self._jwt is None or time.time() - self._jwt_at > 40 * 60:
            self._jwt_at = time.time()
            self._jwt = jwt.encode({"iss": self._team_id, "iat": int(self._jwt_at)}, self._key, algorithm="ES256", headers={"kid": self._key_id})
        return self._jwt

    @staticmethod
    def alert_for(data: dict[str, Any]) -> dict[str, str] | None:
        """The visible notification for an event, or None for events that only refresh an open app."""
        kind = data.get("type")
        if kind == "call.started":
            return {"title": "Pickup is answering a call", "body": str(data.get("caller_display") or "Unknown caller")}
        if kind == "call.live" and data.get("reason"):
            return {"title": f"Live: {data.get('title') or 'Call'}", "body": str(data["reason"])}
        if kind == "summary" and data.get("summary"):
            return {"title": str(data.get("title") or "Call summary"), "body": str(data["summary"])}
        if kind == "takeover.ringing":
            return {"title": "Your phone will ring", "body": "Answer it to talk to the caller."}
        if kind == "line.verified":
            return {"title": "Call forwarding works", "body": "Your assistant will answer the calls you decline or miss."}
        if kind == "call.missed":
            return {"title": f"Missed call: {data.get('title') or 'Unknown caller'}", "body": "It didn't reach your assistant. Tap to call back."}
        if kind == "forwarding.problem":
            return {"title": "Calls aren't reaching your assistant", "body": "Your carrier may have turned off forwarding. Tap to fix it in a minute."}
        return None

    @staticmethod
    def live_activity_payload(data: dict[str, Any], now: int) -> dict[str, Any] | None:
        """The Live Activity push for an event: start when a call begins, update while it's live,
        end when it's over. Keys match CallActivityAttributes in the iPhone app."""
        kind = data.get("type")
        if kind == "call.started":
            title = str(data.get("caller_display") or "Unknown caller")
            state = {"title": title, "reason": "Your assistant is answering", "lastLine": "", "state": "live"}
            return {"aps": {"timestamp": now, "event": "start", "content-state": state, "attributes-type": "CallActivityAttributes",
                            "attributes": {"callId": str(data.get("call_id"))}, "alert": {"title": "Pickup is answering a call", "body": title}}}
        if kind == "call.live":
            lines = data.get("lines") or []
            last = lines[-1] if lines else {}
            speaker = {"caller": "Caller", "assistant": "Assistant", "owner": "You"}.get(last.get("s", ""), "")
            state = {"title": str(data.get("title") or "Call"), "reason": str(data.get("reason") or "Your assistant is talking to them"),
                     "lastLine": f"{speaker}: {last.get('t', '')}" if speaker else "", "state": "live"}
            return {"aps": {"timestamp": now, "event": "update", "content-state": state}}
        if kind == "call.ended":
            state = {"title": str(data.get("title") or "Call"), "reason": "Call ended. The summary is on its way.", "lastLine": "", "state": "ended"}
            return {"aps": {"timestamp": now, "event": "end", "content-state": state, "dismissal-date": now + 15 * 60}}
        return None

    async def _post(self, token: str, body: dict[str, Any], headers: dict[str, str]) -> bool:
        resp = await self._client.post(f"{self._host}/3/device/{token}", json=body, headers=headers)
        if resp.status_code == 200:
            return True
        if resp.status_code == 410 or "BadDeviceToken" in resp.text or "Unregistered" in resp.text:
            await forget_device(token)
        else:
            logger.warning(f"APNs send failed {resp.status_code}: {resp.text[:200]}")
        return False

    async def _live_activity(self, user_id: str, data: dict[str, Any]) -> int:
        payload = self.live_activity_payload(data, int(time.time()))
        call_id = data.get("call_id")
        if payload is None or not call_id:
            return 0
        async with sessionmaker()() as session:
            if data.get("type") == "call.started":
                tokens = (await session.scalars(select(Device.live_activity_start_token).where(
                    Device.user_id == user_id, Device.platform == "ios", Device.live_activity_start_token.is_not(None)))).all()
            else:
                call = await session.get(Call, call_id)
                tokens = [call.live_activity_token] if call and call.live_activity_token else []
        headers = {"authorization": f"bearer {self._bearer()}", "apns-topic": f"{self._topic}.push-type.liveactivity",
                   "apns-push-type": "liveactivity", "apns-priority": "10"}
        sent = 0
        for token in tokens:
            resp = await self._client.post(f"{self._host}/3/device/{token}", json=payload, headers=headers)
            if resp.status_code == 200:
                sent += 1
            else:
                logger.warning(f"Live Activity push failed {resp.status_code}: {resp.text[:200]}")
        return sent

    async def send_to_user(self, user_id: str, data: dict[str, Any], *, collapse_key: str | None = None) -> int:
        live = await self._live_activity(user_id, data)
        alert = self.alert_for(data)
        # A running Live Activity already shows the call; don't also stack alerts for it.
        if alert is None or (live and data.get("type") in ("call.started", "call.live")):
            return live
        async with sessionmaker()() as session:
            tokens = (await session.scalars(select(Device.fcm_token).where(Device.user_id == user_id, Device.platform == "ios"))).all()
        if not tokens:
            return 0
        body = {"aps": {"alert": alert, "sound": "default", "thread-id": str(data.get("call_id") or "pickup")}, "type": data.get("type"), "call_id": data.get("call_id")}
        headers = {"authorization": f"bearer {self._bearer()}", "apns-topic": self._topic, "apns-push-type": "alert", "apns-priority": "10"}
        if collapse_key:
            headers["apns-collapse-id"] = collapse_key[:64]
        sent = live
        for token in tokens:
            if await self._post(token, body, headers):
                sent += 1
        return sent


class MultiPush:
    """Sends through every configured service; each one picks its own devices."""

    def __init__(self, senders: list[PushSender]) -> None:
        self._senders = senders

    async def send_to_user(self, user_id: str, data: dict[str, Any], *, collapse_key: str | None = None) -> int:
        sent = 0
        for sender in self._senders:
            try:
                sent += await sender.send_to_user(user_id, data, collapse_key=collapse_key)
            except Exception as exc:
                logger.warning(f"Push via {type(sender).__name__} failed: {exc}")
        return sent


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
        senders: list[PushSender] = []
        if info:
            senders.append(FcmPush(info))
        else:
            logger.info("FCM not configured: Android push notifications are off")
        if s.apns_key_p8 and s.apns_key_id and s.apple_team_id:
            senders.append(ApnsPush(s.apns_key_p8, s.apns_key_id, s.apple_team_id, s.ios_bundle_id, sandbox=s.apns_sandbox))
        else:
            logger.info("APNs not configured: iPhone push notifications are off")
        _push = MultiPush(senders) if senders else NoopPush()
    return _push


def set_push(sender: PushSender) -> None:
    global _push
    _push = sender
