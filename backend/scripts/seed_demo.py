"""Fill a development database with a realistic demo account (used for app screenshots).

    python -m scripts.seed_demo --phone +919800000002 --pool +918047491800

Creates a user who finished setup, with a verified assistant number, settings, rules, a day of
summarized calls (delivery, scam, recruiter, family, sales), one call still live, and a short
"Ask Pickup" chat. Also puts the --pool numbers into the assistant-number pool. Never run this
against production.
"""

import argparse
import asyncio
from datetime import timedelta

from app.config import get_settings
from app.db import create_all, sessionmaker, utcnow
from app.models import (
    AssistantSettings,
    Call,
    CallAction,
    ChatMessage,
    Line,
    NumberPoolEntry,
    Rule,
    TranscriptSegment,
    User,
)

ASSISTANT_NUMBER = "+918047491899"

CALLS = [
    {
        # A call the carrier never delivered: shows as a missed call with Call back.
        "ago": timedelta(hours=1, minutes=10),
        "from": "+919900445566",
        "mode": "not_reached",
        "caller_name": None,
        "org": None,
        "category": None,
        "reason": "Didn't reach your assistant",
        "summary": "+91 99004 45566 called, but the call didn't reach your assistant: your carrier didn't forward it, or they hung up while it was being forwarded. Call back if you need to.",
        "urgency": "normal",
        "duration": 0,
        "actions": [],
        "transcript": [],
    },
    {
        # TRAI's verified 1600 series: a real bank, never tagged spam.
        "ago": timedelta(hours=3, minutes=5),
        "from": "+911600123456",
        "caller_name": "Rahul",
        "org": "HDFC Bank",
        "category": "bank_finance",
        "reason": "Credit card bill due on 20 November",
        "summary": "Says he's Rahul from HDFC Bank (a verified 1600 bank number): your credit card bill of ₹18,240 is due on 20 November. He didn't ask for any details.",
        "urgency": "normal",
        "duration": 48,
        "actions": [("reminder", "Pay the HDFC card bill by 20 Nov")],
        "transcript": [
            ("assistant", "नमस्ते, मैं Pickup हूँ, Asha की AI assistant. अभी Asha से बात नहीं हो पाएगी. आप कौन बोल रहे हैं?"),
            ("caller", "Hi, this is Rahul from HDFC Bank. Just a reminder that the credit card bill of 18,240 rupees is due on the 20th."),
            ("assistant", "Thanks Rahul. I'll tell Asha the bill of 18,240 rupees is due on 20 November."),
        ],
    },
    {
        "ago": timedelta(minutes=38),
        "from": "+919845012345",
        "caller_name": "Ramesh",
        "org": "Blue Dart",
        "category": "delivery",
        "reason": "Parcel at Gate 2, asked for the delivery OTP",
        "summary": "Ramesh from Blue Dart was at the gate with your parcel. Pickup told him to leave it with the guard at Gate 2 and didn't share the OTP. He'll wait 15 minutes for you to call back.",
        "urgency": "normal",
        "duration": 74,
        "actions": [("call_back", "Call Ramesh back with the OTP")],
        "transcript": [
            ("assistant", "नमस्ते, मैं Pickup हूँ, Asha की AI assistant. अभी Asha से बात नहीं हो पाएगी. आप कौन बोल रहे हैं?"),
            ("caller", "मैं Ramesh बोल रहा हूँ Blue Dart से, parcel है, gate पे खड़ा हूँ."),
            ("assistant", "Ramesh जी, Asha ने बोला है कि parcel Gate 2 पर security guard को दे दीजिए."),
            ("caller", "ठीक है, पर OTP चाहिए होगा."),
            ("assistant", "OTP मैं नहीं बता सकती. मैं Asha को बता देती हूँ, वो आपको इसी number पर call करेंगी."),
        ],
    },
    {
        "ago": timedelta(hours=2, minutes=5),
        "from": "+917428531902",
        "caller_name": None,
        "org": None,
        "category": "scam",
        "reason": "Fake KYC update, threatened to block the bank account",
        "summary": "The caller claimed your bank account would be blocked unless you updated KYC and asked for an OTP. Pickup refused and ended the call. This number has been reported as spam by other users.",
        "urgency": "low",
        "spam": True,
        "duration": 41,
        "actions": [("block", "Block this number")],
        "transcript": [
            ("caller", "Madam your bank account will be blocked today, KYC update pending. Tell me the OTP you received."),
            ("assistant", "I can't share any OTP or bank details. Banks never ask for an OTP on a call. Goodbye."),
        ],
    },
    {
        "ago": timedelta(hours=4, minutes=20),
        "from": "+919900112233",
        "caller_name": "Rohit",
        "org": "TalentEdge",
        "category": "recruiter",
        "reason": "Senior PM role at a Bangalore fintech, ₹45–50L",
        "summary": "Rohit from TalentEdge has a senior product manager role at a fintech in Bangalore: ₹45–50 lakh, hybrid (three days in office). The process closes in two weeks. He asked you to call back tomorrow after 6 PM or email rohit@talentedge.in.",
        "urgency": "normal",
        "duration": 118,
        "actions": [("reminder", "Call Rohit tomorrow after 6 PM"), ("save_contact", "Save Rohit (TalentEdge)")],
        "transcript": [
            ("caller", "Hello, मैं Rohit बोल रहा हूँ TalentEdge से, Asha जी के लिए एक job opportunity है."),
            ("assistant", "ठीक है Rohit जी, मैं Asha तक message पहुँचा दूँगी. Role के बारे में थोड़ा बता दीजिए?"),
            ("caller", "Senior product manager, fintech, Bangalore. Package 45 to 50 lakh, hybrid."),
            ("assistant", "समझ गई. Asha आपको कब call back करें?"),
            ("caller", "कल शाम छह बजे के बाद. Email भी है, rohit at talentedge dot in."),
        ],
    },
    {
        "ago": timedelta(hours=6, minutes=45),
        "from": "+919811122233",
        "known": "Maa",
        "caller_name": None,
        "org": None,
        "category": "personal",
        "reason": "Wanted to confirm Sunday lunch",
        "summary": "Your mother called to check if you're coming for lunch on Sunday. Pickup offered to connect her; she said it's not urgent and asked you to call her in the evening.",
        "urgency": "normal",
        "duration": 52,
        "actions": [("call_back", "Call Maa this evening")],
        "transcript": [
            ("caller", "Asha को बोलना, Sunday lunch पे आ रही है ना? कोई जल्दी नहीं, शाम को call कर ले."),
            ("assistant", "ज़रूर, मैं Asha को बता दूँगी कि शाम को आपको call करें."),
        ],
    },
    {
        "ago": timedelta(days=1, hours=1),
        "from": "+918061234567",
        "caller_name": "Priya",
        "org": "EasyCredit Finance",
        "category": "sales",
        "reason": "Pre-approved personal loan offer",
        "summary": "Priya from EasyCredit Finance offered a pre-approved personal loan. Following your rule for sales calls, Pickup said you're not interested and asked them not to call again.",
        "urgency": "low",
        "duration": 33,
        "actions": [],
        "transcript": [
            ("caller", "Ma'am you have a pre-approved personal loan of 5 lakh at a special rate."),
            ("assistant", "Thanks, but Asha isn't interested. Please don't call this number again. Goodbye."),
        ],
    },
]

LIVE_CALL = {
    "from": "+912226543210",
    "caller_name": "Sunita",
    "org": "Dr. Mehta's Clinic",
    "category": "appointment",
    "reason": "Confirming tomorrow's 5 PM dental appointment",
    "replies": ["Yes, confirm 5 PM", "Can we move it to Monday?", "I'll call back"],
    "transcript": [
        ("assistant", "Hi, this is Pickup, Asha's AI assistant. Asha can't take your call right now. Who's calling?"),
        ("caller", "Hi, this is Sunita from Dr. Mehta's clinic. Calling to confirm Asha's appointment tomorrow at 5 PM."),
        ("assistant", "Thanks Sunita. Let me check with Asha, one moment."),
    ],
}

CHAT = [
    ("user", "Who called today about the job?"),
    ("assistant", "Rohit from TalentEdge, about a senior product manager role at a fintech in Bangalore (₹45–50 lakh, hybrid). He asked you to call back tomorrow after 6 PM. Want a reminder?"),
    ("user", "Yes, remind me at 6"),
    ("assistant", "Done. I'll remind you tomorrow at 6 PM to call Rohit back."),
    ("user", "If Blue Dart calls again, tell them to leave it with the guard"),
    ("assistant", "Got it. I've added that to your delivery note: leave parcels with the guard at Gate 2."),
]


async def seed(phone: str, pool: list[str]) -> None:
    if not get_settings().is_dev:
        raise SystemExit("Refusing to seed demo data into a production database")
    await create_all()
    now = utcnow()
    async with sessionmaker()() as session:
        for number in pool:
            if await session.get(NumberPoolEntry, number) is None:
                session.add(NumberPoolEntry(number=number, provider="exotel"))

        user = User(phone_e164=phone, name="Asha Rao", language="hi-IN", trial_ends_at=now + timedelta(days=5), onboarding_completed_at=now - timedelta(days=3))
        session.add(user)
        await session.flush()
        session.add(NumberPoolEntry(number=ASSISTANT_NUMBER, provider="exotel", state="assigned", user_id=user.id, assigned_at=now - timedelta(days=3)))
        line = Line(user_id=user.id, phone_e164=phone, carrier="Airtel", assistant_number=ASSISTANT_NUMBER, status="verified", verified_at=now - timedelta(days=3))
        session.add(line)
        session.add(
            AssistantSettings(
                user_id=user.id,
                languages=["hi-IN", "en-IN"],
                pack_ids=["deliveries", "sales_calls", "banks", "scam_shield", "family_first"],
                delivery_note="Leave parcels with the guard at Gate 2.",
                instructions="If Ravi from the bank calls about the home loan, ask him to email me.",
            )
        )
        session.add(Rule(user_id=user.id, match_type="category", match_value="sales", action="decline"))
        session.add(Rule(user_id=user.id, match_type="category", match_value="personal", action="connect"))
        await session.flush()

        def add_call(spec: dict, state: str, started) -> Call:
            call = Call(
                user_id=user.id, line_id=line.id, provider="exotel", mode=spec.get("mode", "screen"), from_number=spec["from"], to_number=ASSISTANT_NUMBER,
                caller_known_name=spec.get("known"), caller_name=spec.get("caller_name"), caller_org=spec.get("org"),
                category=spec["category"], reason=spec["reason"], urgency=spec.get("urgency", "normal"),
                is_spam=spec.get("spam", False), suggested_replies=spec.get("replies", []), summary=spec.get("summary"),
                state=state, started_at=started, answered_at=started,
            )
            if state == "summarized":
                call.ended_at = started + timedelta(seconds=spec["duration"])
                call.duration_seconds = spec["duration"]
                call.end_reason = "completed"
            session.add(call)
            return call

        for spec in CALLS:
            call = add_call(spec, "summarized", now - spec["ago"])
            await session.flush()
            for seq, (speaker, text) in enumerate(spec["transcript"]):
                session.add(TranscriptSegment(call_id=call.id, seq=seq, speaker=speaker, text=text, created_at=call.started_at + timedelta(seconds=6 * seq)))
            for kind, title in spec["actions"]:
                session.add(CallAction(call_id=call.id, user_id=user.id, type=kind, title=title, payload={}))

        live = add_call(LIVE_CALL, "live", now - timedelta(seconds=40))
        await session.flush()
        for seq, (speaker, text) in enumerate(LIVE_CALL["transcript"]):
            session.add(TranscriptSegment(call_id=live.id, seq=seq, speaker=speaker, text=text, created_at=live.started_at + timedelta(seconds=8 * seq)))

        for i, (role, text) in enumerate(CHAT):
            session.add(ChatMessage(user_id=user.id, role=role, text=text, content=[{"type": "text", "text": text}], created_at=now - timedelta(minutes=30 - i)))
        await session.commit()
    print(f"Seeded demo user {phone} with {len(CALLS)} calls, 1 live call and {len(CHAT)} chat messages")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    parser.add_argument("--pool", nargs="*", default=[])
    args = parser.parse_args()
    asyncio.run(seed(args.phone, args.pool))


if __name__ == "__main__":
    main()
