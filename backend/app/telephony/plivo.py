"""Plivo: Voice API answer URLs + bidirectional Audio Streams."""

from typing import Any

from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.telephony.base import InboundCall, TelephonyProvider, media_token, media_ws_url, public_url, x, xa, xml_response


class PlivoProvider(TelephonyProvider):
    name = "plivo"

    def __init__(self) -> None:
        s = get_settings()
        self._auth_id = s.plivo_auth_id
        self._auth_token = s.plivo_auth_token
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(self._auth_id and self._auth_token)

    def client(self):
        if self._client is None:
            import plivo

            self._client = plivo.RestClient(self._auth_id, self._auth_token)
        return self._client

    async def validate(self, request: Request, params: dict[str, Any]) -> bool:
        if not self.configured:
            return get_settings().is_dev
        from plivo.utils.signature_v3 import validate_v3_signature

        url = public_url(request.url.path) + (f"?{request.url.query}" if request.url.query else "")
        signature = request.headers.get("X-Plivo-Signature-V3", "")
        nonce = request.headers.get("X-Plivo-Signature-V3-Nonce", "")
        try:
            return bool(validate_v3_signature(request.method, url, nonce, self._auth_token, signature, params))
        except Exception:
            return False

    def parse_inbound(self, params: dict[str, Any]) -> InboundCall:
        return InboundCall(
            provider_call_id=params.get("CallUUID"),
            from_number=params.get("From"),
            to_number=params.get("To"),
            forwarded_from=params.get("ForwardedFrom"),
        )

    def stream_response(self, call_id: str) -> Response:
        url = media_ws_url(call_id)
        return xml_response(
            f'<Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">{x(url)}</Stream>'
        )

    def say_and_hangup(self, text: str) -> Response:
        return xml_response(f"<Speak>{x(text)}</Speak><Hangup/>")

    def dial_response(self, to_number: str, caller_id: str) -> Response:
        return xml_response(f"<Dial callerId={xa(caller_id)} timeout=\"30\"><Number>{x(to_number)}</Number></Dial>")

    async def transfer(self, *, call_id: str, provider_call_id: str, to_number: str, caller_id: str) -> bool:
        url = public_url(f"/telephony/plivo/transfer/{call_id}/{media_token(call_id)}")
        await run_in_threadpool(lambda: self.client().calls.transfer(provider_call_id, legs="aleg", aleg_url=url, aleg_method="POST"))
        return True

    async def place_call(self, *, to_number: str, from_number: str, call_id: str, purpose: str) -> str | None:
        token = media_token(call_id)
        answer = public_url(f"/telephony/plivo/answer/{call_id}/{token}")
        hangup = public_url(f"/telephony/plivo/status/{call_id}/{token}")

        def _create():
            return self.client().calls.create(
                from_=from_number.lstrip("+"), to_=to_number.lstrip("+"), answer_url=answer, answer_method="POST", hangup_url=hangup
            )

        resp = await run_in_threadpool(_create)
        request_uuid = getattr(resp, "request_uuid", None)
        return request_uuid if isinstance(request_uuid, str) else None

    async def hangup(self, provider_call_id: str) -> None:
        await run_in_threadpool(lambda: self.client().calls.hangup(provider_call_id))
