"""Twilio: Programmable Voice webhooks + bidirectional Media Streams.

Note: Twilio cannot place domestic India-to-India calls, so use it for other markets.
"""

from typing import Any

from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.telephony.base import InboundCall, TelephonyProvider, media_token, media_ws_url, public_url, x, xa, xml_response


class TwilioProvider(TelephonyProvider):
    name = "twilio"

    def __init__(self) -> None:
        s = get_settings()
        self._sid = s.twilio_account_sid
        self._token = s.twilio_auth_token
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(self._sid and self._token)

    def client(self):
        if self._client is None:
            from twilio.rest import Client

            self._client = Client(self._sid, self._token)
        return self._client

    async def validate(self, request: Request, params: dict[str, Any]) -> bool:
        if not self.configured:
            return get_settings().is_dev
        from twilio.request_validator import RequestValidator

        url = public_url(request.url.path) + (f"?{request.url.query}" if request.url.query else "")
        signature = request.headers.get("X-Twilio-Signature", "")
        return RequestValidator(self._token).validate(url, params, signature)

    def parse_inbound(self, params: dict[str, Any]) -> InboundCall:
        return InboundCall(
            provider_call_id=params.get("CallSid"),
            from_number=params.get("From"),
            to_number=params.get("To") or params.get("Called"),
            forwarded_from=params.get("ForwardedFrom"),
        )

    def stream_response(self, call_id: str) -> Response:
        url = media_ws_url(call_id)
        return xml_response(f'<Connect><Stream url={xa(url)}><Parameter name="call_id" value={xa(call_id)}/></Stream></Connect>')

    def say_and_hangup(self, text: str) -> Response:
        return xml_response(f"<Say>{x(text)}</Say><Hangup/>")

    async def transfer(self, *, call_id: str, provider_call_id: str, to_number: str, caller_id: str) -> bool:
        twiml = f'<Response><Dial callerId={xa(caller_id)} timeout="30">{x(to_number)}</Dial></Response>'
        await run_in_threadpool(lambda: self.client().calls(provider_call_id).update(twiml=twiml))
        return True

    async def place_call(self, *, to_number: str, from_number: str, call_id: str, purpose: str) -> str | None:
        answer = public_url(f"/telephony/twilio/answer/{call_id}/{media_token(call_id)}")
        status = public_url(f"/telephony/twilio/status/{call_id}/{media_token(call_id)}")

        def _create():
            return self.client().calls.create(
                to=to_number,
                from_=from_number,
                url=answer,
                status_callback=status,
                status_callback_event=["completed"],
                timeout=30,
            )

        call = await run_in_threadpool(_create)
        return call.sid

    async def hangup(self, provider_call_id: str) -> None:
        await run_in_threadpool(lambda: self.client().calls(provider_call_id).update(status="completed"))
