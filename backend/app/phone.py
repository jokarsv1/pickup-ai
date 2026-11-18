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


# TRAI's numbering series for regulated business calls (TCCCPR Third Amendment, 18 Sep 2026).
# Call-management apps must not spam-tag, blanket block or filter these; users may choose to.
DESIGNATED_SERIES = (
    ("+911600", "bank_gov"),  # banks, insurers, funds, government: service and transactional
    ("+911601", "service"),  # service and transactional calls from other sectors (courier, utilities)
    ("+91140", "promo"),  # registered telemarketers: promotional
)

SERIES_LABELS = {
    "bank_gov": "Verified bank or government number",
    "service": "Verified service number",
    "promo": "Registered promotional number",
}


def designated_series(e164: str | None) -> str | None:
    """bank_gov, service or promo for TRAI's designated business series, else None."""
    if not e164:
        return None
    for prefix, kind in DESIGNATED_SERIES:
        if e164.startswith(prefix):
            return kind
    return None


def reputation_hash(e164: str) -> str:
    """Salted hash so the shared reputation table never stores raw caller numbers."""
    salt = get_settings().jwt_secret
    return hashlib.sha256(f"{salt}:{e164}".encode()).hexdigest()
