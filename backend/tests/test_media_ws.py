"""The media WebSocket accepts a Twilio-format stream and, with no AI keys configured, ends the
call cleanly instead of leaving the caller in silence."""

import json

from sqlalchemy import select

from app.db import sessionmaker
from app.models import Call
from app.routers.telephony import media
from app.telephony.base import media_token
from tests.conftest import setup_line, sign_in


class FakeWebSocket:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = [json.dumps(m) for m in messages]
        self.accepted = False
        self.closed_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code

    async def iter_text(self):
        for message in self._messages:
            yield message


async def test_media_stream_without_keys_ends_call(app_env):
    c = app_env.client
    headers = await sign_in(c)
    await setup_line(c, headers)
    await c.post("/telephony/twilio/inbound", data={"CallSid": "CA1", "From": "+917011112222", "To": "+918047491899"})
    async with sessionmaker()() as s:
        call = await s.scalar(select(Call).where(Call.provider_call_id == "CA1"))

    rejected = FakeWebSocket([])
    await media(rejected, call.id, "bad-token")
    assert rejected.closed_code == 4403 and not rejected.accepted

    ws = FakeWebSocket(
        [
            {"event": "connected", "protocol": "Call", "version": "1.0.0"},
            {"event": "start", "start": {"streamSid": "MZ1", "callSid": "CA1", "accountSid": "AC1", "customParameters": {}}, "streamSid": "MZ1"},
        ]
    )
    await media(ws, call.id, media_token(call.id))
    async with sessionmaker()() as s:
        ended = await s.get(Call, call.id)
    assert ws.accepted and ended.end_reason == "voice_unavailable" and ended.ended_at is not None
