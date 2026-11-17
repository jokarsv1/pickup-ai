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


async def test_apns_push_to_iphone(app_env):
    """iPhones get a signed, visible alert collapsed per call; Android devices are left to FCM."""
    import jwt as pyjwt
    import respx
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from httpx import Response

    from app.db import sessionmaker
    from app.models import Device, User
    from app.push import ApnsPush

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    async with sessionmaker()() as session:
        user = User(phone_e164="+919811100009")
        session.add(user)
        await session.flush()
        session.add_all([Device(user_id=user.id, fcm_token="iphone-token", platform="ios"), Device(user_id=user.id, fcm_token="android-token", platform="android")])
        await session.commit()
        user_id = user.id

    apns = ApnsPush(pem, "KEY123", "TEAM456", "ai.pickup.app")
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://api.push.apple.com/3/device/iphone-token").mock(return_value=Response(200))
        sent = await apns.send_to_user(user_id, {"type": "summary", "call_id": "call_1", "title": "Rohit · TalentEdge", "summary": "Job offer"}, collapse_key="call_1")
    assert sent == 1
    request = route.calls.last.request
    assert request.headers["apns-topic"] == "ai.pickup.app" and request.headers["apns-collapse-id"] == "call_1"
    claims = pyjwt.decode(request.headers["authorization"].split()[1], key.public_key(), algorithms=["ES256"])
    assert claims["iss"] == "TEAM456"
    assert b"Rohit" in request.content and b"Job offer" in request.content
    # Transcript lines only refresh an open app: no alert.
    assert await apns.send_to_user(user_id, {"type": "transcript", "text": "hi"}) == 0


async def test_live_activity_pushes(app_env):
    """iPhones get a Live Activity: started by push when a call begins, updated, then ended."""
    import json as jsonlib

    import respx
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from httpx import Response

    from app.db import sessionmaker
    from app.models import Call, Device, User
    from app.push import ApnsPush

    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    async with sessionmaker()() as session:
        user = User(phone_e164="+919811100010")
        session.add(user)
        await session.flush()
        session.add(Device(user_id=user.id, fcm_token="iphone-token", platform="ios", live_activity_start_token="start-token"))
        call = Call(user_id=user.id, provider="exotel", state="live")
        session.add(call)
        await session.commit()
        user_id, call_id = user.id, call.id

    apns = ApnsPush(pem, "KEY123", "TEAM456", "ai.pickup.app")
    with respx.mock(assert_all_called=False) as mock:
        start = mock.post("https://api.push.apple.com/3/device/start-token").mock(return_value=Response(200))
        alert = mock.post("https://api.push.apple.com/3/device/iphone-token").mock(return_value=Response(200))
        await apns.send_to_user(user_id, {"type": "call.started", "call_id": call_id, "caller_display": "+91 98450 12345"})
        body = jsonlib.loads(start.calls.last.request.content)
        assert start.calls.last.request.headers["apns-topic"] == "ai.pickup.app.push-type.liveactivity"
        assert body["aps"]["event"] == "start" and body["aps"]["attributes"] == {"callId": call_id}
        assert not alert.called  # the Live Activity replaces the "answering a call" alert

        # The phone reports the activity's own token; updates and the end go there.
        async with sessionmaker()() as session:
            (await session.get(Call, call_id)).live_activity_token = "activity-token"
            await session.commit()
        update = mock.post("https://api.push.apple.com/3/device/activity-token").mock(return_value=Response(200))
        await apns.send_to_user(user_id, {"type": "call.live", "call_id": call_id, "title": "Ramesh · Blue Dart", "reason": "Parcel at the gate", "lines": [{"s": "caller", "t": "OTP chahiye"}]})
        state = jsonlib.loads(update.calls.last.request.content)["aps"]["content-state"]
        assert state == {"title": "Ramesh · Blue Dart", "reason": "Parcel at the gate", "lastLine": "Caller: OTP chahiye", "state": "live"}
        await apns.send_to_user(user_id, {"type": "call.ended", "call_id": call_id, "title": "Ramesh · Blue Dart"})
        assert jsonlib.loads(update.calls.last.request.content)["aps"]["event"] == "end"
