"""Provider-neutral telephony interface.

Every provider does the same four jobs for Pickup:
  1. Tell us a call arrived at an assistant number, and stream its audio to our WebSocket.
  2. Transfer a live call to the user's own phone (take over).
  3. Place outbound calls (assistant calls for the user, and the forwarding verification call).
  4. Hang up.
"""

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from fastapi import Request, Response

from app.config import get_settings


@dataclass
class InboundCall:
    provider_call_id: str | None
    from_number: str | None
    to_number: str | None
    forwarded_from: str | None = None


def media_token(call_id: str) -> str:
    secret = get_settings().telephony_webhook_secret.encode()
    return hmac.new(secret, call_id.encode(), hashlib.sha256).hexdigest()[:32]


def verify_media_token(call_id: str, token: str) -> bool:
    return hmac.compare_digest(media_token(call_id), token)


def media_ws_url(call_id: str) -> str:
    """Path-only parameters: Twilio stream URLs don't allow query strings."""
    return f"{get_settings().public_ws_base_url}/telephony/media/{call_id}/{media_token(call_id)}"


def public_url(path: str) -> str:
    return f"{get_settings().public_base_url}{path}"


def xml_response(body: str) -> Response:
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>', media_type="application/xml")


def x(text: str) -> str:
    return escape(text)


def xa(text: str) -> str:
    return quoteattr(text)


class TelephonyProvider(ABC):
    name: str

    @abstractmethod
    async def validate(self, request: Request, params: dict[str, Any]) -> bool: ...

    @abstractmethod
    def parse_inbound(self, params: dict[str, Any]) -> InboundCall: ...

    @abstractmethod
    def stream_response(self, call_id: str) -> Response:
        """Answer the call and stream its audio to the voice agent."""

    @abstractmethod
    def say_and_hangup(self, text: str) -> Response: ...

    @abstractmethod
    async def transfer(self, *, call_id: str, provider_call_id: str, to_number: str, caller_id: str) -> bool:
        """Move the caller to the user's phone. Returns False if the voice agent must end the stream itself."""

    @abstractmethod
    async def place_call(self, *, to_number: str, from_number: str, call_id: str, purpose: str) -> str | None:
        """Start an outbound call. Returns the provider's call id."""

    @abstractmethod
    async def hangup(self, provider_call_id: str) -> None: ...

    @property
    def configured(self) -> bool:
        return True
