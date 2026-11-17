import asyncio

from app.ai.prompts import CallContext, greeting_for, voice_system_prompt
from app.forwarding import activation_codes, carrier_note, clamp_ring_seconds
from app.phone import normalize, pretty
from app.push import NoopPush, Throttle
from app.telephony.base import media_token, media_ws_url, verify_media_token


def test_normalize_handles_indian_formats():
    assert normalize("09876543210") == "+919876543210"
    assert normalize("919876543210") == "+919876543210"
    assert normalize("+91 98765 43210") == "+919876543210"
    assert normalize("98765 43210") == "+919876543210"
    assert normalize("anonymous") is None
    assert normalize("12") is None
    assert pretty("+919876543210").startswith("+91")


def test_forwarding_codes_use_gsm_standard():
    codes = {c.key: c.code for c in activation_codes("+918047491899", ring_seconds=17)}
    assert codes["busy"] == "**67*+918047491899#"
    assert codes["no_answer"] == "**61*+918047491899**15#"
    assert codes["unreachable"] == "**62*+918047491899#"
    assert clamp_ring_seconds(2) == 5 and clamp_ring_seconds(99) == 30
    assert "SMS" in (carrier_note("Jio 4G") or "")


def test_media_tokens_are_bound_to_call():
    token = media_token("call_abc")
    assert verify_media_token("call_abc", token)
    assert not verify_media_token("call_xyz", token)
    assert media_ws_url("call_abc").startswith("wss://api.example.com/telephony/media/call_abc/")


def test_prompt_contains_instructions_and_rules():
    ctx = CallContext(
        mode="screen",
        owner_name="Asha Rao",
        assistant_name="Pickup",
        languages=["hi-IN", "en-IN"],
        caller_number="+919876543210",
        caller_known_name="Landlord",
        pack_ids=["deliveries", "scam_shield"],
        instructions="Tell my landlord I'll call after 6.",
        delivery_note="Leave parcels with the guard.",
        rules_text=["Callers about Sales or promotion: politely decline and end the call quickly."],
    )
    prompt = voice_system_prompt(ctx)
    assert "Asha" in prompt and "Landlord" in prompt
    assert "Leave parcels with the guard." in prompt
    assert "Never claim to be human" in prompt
    assert "connect_owner" in prompt
    greeting = greeting_for(ctx)
    assert "नमस्ते" in greeting and "Asha की AI assistant" in greeting
    assert "Asha से बात नहीं हो पाएगी" in greeting and "ले पा रहे" not in greeting  # no guessed gender for the owner
    assert "मैं बता सकती हूँ" in prompt
    ctx.assistant_gender = "male"
    assert "Asha का AI assistant" in greeting_for(ctx)
    assert "मैं बता सकता हूँ" in voice_system_prompt(ctx)
    assert "recorded" in greeting_for(CallContext("screen", "Asha", "Pickup", ["en-IN"], None))


async def test_throttle_coalesces_bursts():
    push = NoopPush()
    throttle = Throttle(push, interval=0.2)
    for i in range(5):
        await throttle.send("k", "u1", {"n": i})
    assert [d["n"] for _, d in push.sent] == [0]
    await asyncio.sleep(0.3)
    assert [d["n"] for _, d in push.sent] == [0, 4]


def test_voice_gender():
    from app.voice.services import voice_gender

    assert voice_gender("ritu") == "female" and voice_gender("shubh") == "male"
    assert voice_gender("dev") == "male" and voice_gender(None) == "female" and voice_gender("unknown") == "female"
