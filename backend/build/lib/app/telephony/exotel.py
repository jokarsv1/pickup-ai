"""Exotel (India): AgentStream bidirectional streaming through a call flow.

Flow to build once in Exotel's App Bazaar (see docs/SETUP.md), attached to every ExoPhone
used as an assistant number:

    Voicebot applet   URL = https://API/telephony/exotel/{secret}/voicebot   (returns the wss URL)
    Passthru applet   URL = https://API/telephony/exotel/{secret}/passthru   (200 = user wants to join)
      on 200 -> Connect applet  URL = https://API/telephony/exotel/{secret}/connect
      else   -> Hangup

Exotel puts the caller and ExoPhone numbers in the stream's `start` message, so routing happens
when the WebSocket opens.
"""

from typing import Any

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.telephony.base import InboundCall, TelephonyProvider, public_url


class ExotelProvider(TelephonyProvider):
    name = "exotel"

    def __init__(self) -> None:
        s = get_settings()
        self._sid = s.exotel_account_sid
        self._key = s.exotel_api_key
        self._token = s.exotel_api_token
        self._subdomain = s.exotel_subdomain
        self._flow_id = s.exotel_outbound_flow_id

    @property
    def configured(self) -> bool:
        return bool(self._sid and self._key and self._token)

    async def validate(self, request: Request, params: dict[str, Any]) -> bool:
        # Exotel webhooks are authenticated by the secret embedded in the flow URLs.
        return True

    def parse_inbound(self, params: dict[str, Any]) -> InboundCall:
        return InboundCall(
            provider_call_id=params.get("CallSid"),
            from_number=params.get("CallFrom") or params.get("From"),
            to_number=params.get("CallTo") or params.get("To"),
        )

    def stream_response(self, call_id: str) -> Response:
        from app.telephony.base import media_ws_url

        return JSONResponse({"url": media_ws_url(call_id)})

    def say_and_hangup(self, text: str) -> Response:
        return JSONResponse({"url": ""}, status_code=404)

    async def transfer(self, *, call_id: str, provider_call_id: str, to_number: str, caller_id: str) -> bool:
        # The voice agent closes the stream; the flow's Passthru then Connect applets dial the user.
        return False

    async def place_call(self, *, to_number: str, from_number: str, call_id: str, purpose: str) -> str | None:
        if not self._flow_id:
            raise RuntimeError("EXOTEL_OUTBOUND_FLOW_ID is not set")
        s = get_settings()
        url = f"https://{self._subdomain}/v1/Accounts/{self._sid}/Calls/connect.json"
        data = {
            "From": to_number,  # Exotel dials "From" first, then runs the flow
            "CallerId": from_number,
            "Url": f"http://my.exotel.com/{self._sid}/exoml/start_voice/{self._flow_id}",
            "CallType": "trans",
            "CustomField": call_id,
            "StatusCallback": public_url(f"/telephony/exotel/{s.telephony_webhook_secret}/status"),
        }
        async with httpx.AsyncClient(timeout=15, auth=(self._key or "", self._token or "")) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            body = resp.json()
        return (body.get("Call") or {}).get("Sid")

    async def hangup(self, provider_call_id: str) -> None:
        # Exotel ends the call when the flow finishes; closing the stream is enough.
        return None
