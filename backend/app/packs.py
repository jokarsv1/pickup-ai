"""Call categories and ready-made instruction packs the user can switch on with one tap."""

from dataclasses import dataclass

CATEGORIES: dict[str, str] = {
    "delivery": "Delivery or courier",
    "bank_finance": "Bank, loan or card",
    "sales": "Sales or promotion",
    "recruiter": "Job or recruiter",
    "appointment": "Appointment or service",
    "personal": "Friend or family",
    "government": "Government or official",
    "scam": "Likely scam",
    "survey": "Survey or feedback",
    "other": "Other",
}


@dataclass(frozen=True)
class InstructionPack:
    id: str
    title: str
    subtitle: str
    instructions: str


PACKS: list[InstructionPack] = [
    InstructionPack(
        "deliveries",
        "Deliveries",
        "Handles couriers and delivery agents",
        "For delivery and courier calls: find out which company it is and what they need (an OTP, payment, "
        "where to leave it). Don't ask what's inside the parcel. "
        "If the user saved a delivery note, share it (for example where to leave the parcel). "
        "Never read out an OTP or address unless the user relays it to you during the call.",
    ),
    InstructionPack(
        "sales_calls",
        "Sales calls",
        "Declines loans, cards, insurance pitches",
        "For sales, loan, credit card, insurance or promotional calls: politely say the user is not "
        "interested, ask them to remove this number from their list, and end the call quickly.",
    ),
    InstructionPack(
        "banks",
        "Banks",
        "Takes a message, never shares details",
        "For banks and financial institutions: take a message with the reason and a callback number. "
        "Never confirm account details, card numbers or OTPs. If they ask for any, end the call and "
        "mark it as a likely scam.",
    ),
    InstructionPack(
        "scam_shield",
        "Scam shield",
        "Spots KYC, parcel and police scams",
        "Treat these as likely scams: KYC or SIM expiry warnings, parcels seized by customs or police, "
        "CBI or police threats, lottery wins, UPI refunds, requests to install apps or press keys. "
        "Do not engage. Say the user will not continue, and end the call.",
    ),
    InstructionPack(
        "recruiters",
        "Recruiters",
        "Collects role, company and contact",
        "For recruiters: get the company, the role, the salary range if offered, and the best way to "
        "reply. Say the user will get back if interested.",
    ),
    InstructionPack(
        "family_first",
        "Family first",
        "Connects urgent personal calls",
        "If the caller says they are family or a friend and it is urgent, offer to connect them to "
        "the user right away.",
    ),
    InstructionPack(
        "appointments",
        "Appointments",
        "Confirms clinic and service bookings",
        "For clinics, salons and service bookings: note the date, time and place. If they want a "
        "confirmation, say the user will confirm by message.",
    ),
]

PACKS_BY_ID = {p.id: p for p in PACKS}


def pack_instructions(pack_ids: list[str]) -> list[str]:
    return [PACKS_BY_ID[p].instructions for p in pack_ids if p in PACKS_BY_ID]
