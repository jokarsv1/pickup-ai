import copy
import os
import tempfile
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

_tmp = tempfile.mkdtemp(prefix="pickup-test-")
os.environ.update(
    ENV="test",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/test.db",
    JWT_SECRET="test-secret-test-secret-test-secret-0123",
    ADMIN_TOKEN="admin-test",
    TELEPHONY_PROVIDER="twilio",
    TELEPHONY_WEBHOOK_SECRET="hook-secret",
    RECORDINGS_DIR=f"{_tmp}/recordings",
    PUBLIC_BASE_URL="https://api.example.com",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import Request, Response  # noqa: E402

from app.ai import llm as llm_module  # noqa: E402
from app.db import Base, engine, init_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.push import NoopPush, set_push  # noqa: E402
from app.telephony.base import InboundCall, TelephonyProvider, xml_response  # noqa: E402
from app.telephony.registry import set_provider  # noqa: E402


class FakeLLM:
    def __init__(self) -> None:
        self.structured_results: dict[str, list[Any]] = {}
        self.create_results: list[Any] = []
        self.calls: list[dict[str, Any]] = []

    def queue_structured(self, schema_name: str, value: Any) -> None:
        self.structured_results.setdefault(schema_name, []).append(value)

    def queue_create(self, content: list[dict], stop_reason: str = "end_turn") -> None:
        self.create_results.append(SimpleNamespace(content=content, stop_reason=stop_reason))

    async def structured(self, *, system: str, prompt: str, schema, effort: str = "low", max_tokens: int = 4000):
        self.calls.append({"kind": "structured", "schema": schema.__name__, "prompt": prompt})
        queue = self.structured_results.get(schema.__name__) or []
        if not queue:
            raise llm_module.LLMError("no fake result queued")
        return queue.pop(0)

    async def create(self, *, system: str, messages, tools, effort: str = "medium", max_tokens: int = 8000):
        self.calls.append({"kind": "create", "messages": copy.deepcopy(messages)})
        if not self.create_results:
            raise llm_module.LLMError("no fake result queued")
        return self.create_results.pop(0)


class FakeProvider(TelephonyProvider):
    name = "twilio"

    def __init__(self) -> None:
        self.placed: list[dict[str, Any]] = []
        self.transfers: list[dict[str, Any]] = []

    async def validate(self, request: Request, params: dict[str, Any]) -> bool:
        return True

    def parse_inbound(self, params: dict[str, Any]) -> InboundCall:
        return InboundCall(params.get("CallSid"), params.get("From"), params.get("To"))

    def stream_response(self, call_id: str) -> Response:
        from app.telephony.base import media_ws_url

        return xml_response(f'<Connect><Stream url="{media_ws_url(call_id)}"/></Connect>')

    def say_and_hangup(self, text: str) -> Response:
        return xml_response(f"<Say>{text}</Say><Hangup/>")

    async def transfer(self, *, call_id: str, provider_call_id: str, to_number: str, caller_id: str) -> bool:
        self.transfers.append({"call_id": call_id, "to": to_number, "caller_id": caller_id})
        return True

    async def place_call(self, *, to_number: str, from_number: str, call_id: str, purpose: str) -> str | None:
        self.placed.append({"to": to_number, "from": from_number, "call_id": call_id, "purpose": purpose})
        return f"CA{len(self.placed)}"

    async def hangup(self, provider_call_id: str) -> None:
        return None


@pytest.fixture
async def app_env() -> AsyncIterator[SimpleNamespace]:
    init_engine(os.environ["DATABASE_URL"])
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    fake_llm = FakeLLM()
    llm_module.set_llm(fake_llm)
    push = NoopPush()
    set_push(push)
    import app.services.calls as calls_module

    calls_module._live_throttle = None
    from app import ratelimit

    ratelimit.reset()
    provider = FakeProvider()
    set_provider("twilio", provider)
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://api.example.com") as client:
            yield SimpleNamespace(client=client, llm=fake_llm, push=push, provider=provider, app=app)
    set_provider("twilio", None)
    llm_module.set_llm(None)


async def sign_in(client: httpx.AsyncClient, phone: str = "+919876543210") -> dict[str, str]:
    resp = await client.post("/v1/auth/dev", json={"phone": phone, "code": "123456"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def add_pool_numbers(client: httpx.AsyncClient, *numbers: str) -> None:
    resp = await client.post(
        "/admin/numbers", json=[{"number": n, "provider": "twilio"} for n in numbers], headers={"X-Admin-Token": "admin-test"}
    )
    assert resp.status_code == 200, resp.text


async def setup_line(client: httpx.AsyncClient, headers: dict[str, str], assistant: str = "+918047491899") -> dict:
    await add_pool_numbers(client, assistant)
    resp = await client.post("/v1/lines", json={"carrier": "Jio"}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()
