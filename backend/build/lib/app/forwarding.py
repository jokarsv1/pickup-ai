"""Carrier call-forwarding codes (GSM/3GPP supplementary service MMI codes).

Android only lets the default dialer auto-dial call-forwarding codes, so the app opens the
dialer with each code filled in and the user taps Call. The codes below are the 3GPP
standard set used by Jio, Airtel, Vi and BSNL in India and by most GSM/VoLTE networks.

  **67*N#        forward when busy (also used when the app declines a call)
  **61*N**T#     forward when unanswered after T seconds (5-30, steps of 5)
  **62*N#        forward when unreachable (phone off / no signal)
  ##004#         erase all conditional forwarding (turns the assistant off)
  ##002#         erase all forwarding including unconditional (fallback)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ForwardingCode:
    key: str
    title: str
    description: str
    code: str


def clamp_ring_seconds(seconds: int) -> int:
    seconds = max(5, min(30, seconds))
    return seconds - seconds % 5


def activation_codes(assistant_number: str, ring_seconds: int = 20) -> list[ForwardingCode]:
    n = assistant_number
    t = clamp_ring_seconds(ring_seconds)
    return [
        ForwardingCode(
            "busy",
            "When you decline or are on a call",
            "Pickup declines unknown callers for you, so this is the one that matters most.",
            f"**67*{n}#",
        ),
        ForwardingCode(
            "no_answer",
            f"When you don't pick up within {t} seconds",
            "Calls you miss go to your assistant instead of voicemail.",
            f"**61*{n}**{t}#",
        ),
        ForwardingCode(
            "unreachable",
            "When your phone is off or has no signal",
            "Your assistant still answers on flights and in dead zones.",
            f"**62*{n}#",
        ),
    ]


DEACTIVATE_CODE = "##004#"
DEACTIVATE_ALL_CODE = "##002#"
STATUS_CODES = {"busy": "*#67#", "no_answer": "*#61#", "unreachable": "*#62#"}

CARRIER_NOTES = {
    "jio": "Jio sends an SMS confirming each forwarding change. That's expected.",
    "airtel": "Airtel sends an SMS confirming each forwarding change. That's expected.",
    "vi": "Vi sends an SMS confirming each forwarding change. That's expected.",
    "bsnl": "BSNL may take a minute to apply the change.",
}


def carrier_note(carrier: str | None) -> str | None:
    if not carrier:
        return None
    lowered = carrier.lower()
    for key, note in CARRIER_NOTES.items():
        if key in lowered:
            return note
    return None
