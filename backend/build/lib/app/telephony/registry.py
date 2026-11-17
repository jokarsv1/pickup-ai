from functools import cache

from app.config import get_settings
from app.telephony.base import TelephonyProvider
from app.telephony.exotel import ExotelProvider
from app.telephony.plivo import PlivoProvider
from app.telephony.twilio import TwilioProvider

_overrides: dict[str, TelephonyProvider] = {}


@cache
def _build(name: str) -> TelephonyProvider:
    return {"exotel": ExotelProvider, "plivo": PlivoProvider, "twilio": TwilioProvider}[name]()


def get_provider(name: str | None = None) -> TelephonyProvider:
    name = name or get_settings().telephony_provider
    return _overrides.get(name) or _build(name)


def set_provider(name: str, provider: TelephonyProvider | None) -> None:
    """Test hook."""
    if provider is None:
        _overrides.pop(name, None)
    else:
        _overrides[name] = provider
