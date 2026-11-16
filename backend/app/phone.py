"""Phone number helpers built on Google's libphonenumber port."""

import hashlib

import phonenumbers

from app.config import get_settings


def normalize(raw: str | None, region: str | None = None) -> str | None:
    """Return E.164 (+919876543210) or None when the input is not a valid number.

    Telephony providers send numbers in many shapes: "09876543210", "919876543210",
    "+91 98765 43210". Indian carriers also prefix forwarded calls with "0".
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in {"anonymous", "unknown", "private", "restricted"}:
        return None
    region = region or get_settings().default_country
    candidates = [raw]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits and not raw.startswith("+"):
        candidates.append("+" + digits)  # "919876543210" style
    for candidate in candidates:
        try:
            parsed = phonenumbers.parse(candidate, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return None


def pretty(e164: str | None) -> str:
    if not e164:
        return "Unknown number"
    try:
        parsed = phonenumbers.parse(e164, None)
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        return e164


def reputation_hash(e164: str) -> str:
    """Salted hash so the shared reputation table never stores raw caller numbers."""
    salt = get_settings().jwt_secret
    return hashlib.sha256(f"{salt}:{e164}".encode()).hexdigest()
