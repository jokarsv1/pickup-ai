import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.ai.schemas import CallInsights, LiveIntent, SuggestedAction
from app.ai.understanding import LiveIntentTracker, summarize_call
from app.db import sessionmaker, utcnow
from app.events import bus, call_topic, user_topic
from app.models import Call, Line, OutboundTask, User
from app.services import calls as call_service
from app.services.outbound import dial
from tests.conftest import setup_line, sign_in


async def test_sign_in_creates_trial_and_refresh_rotates(app_env):
    c = app_env.client
    cfg = (await c.get("/v1/config")).json()
    assert "dev" in cfg["auth_modes"] and cfg["voice_ready"] is False
    resp = await c.post("/v1/auth/dev", json={"phone": "09876543210", "code": "123456"})
    body = resp.json()
    assert body["is_new_user"] and body["user"]["phone"] == "+919876543210"
    bad = await c.post("/v1/auth/dev", json={"phone": "09876543210", "code": "000000"})
    assert bad.status_code == 401
    r2 = await c.post("/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r2.status_code == 200
    reused = await c.post("/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert reused.status_code == 401
    headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    me = await c.patch("/v1/me", json={"name": "Asha Rao", "onboarding_completed": True}, headers=headers)
    assert me.json()["name"] == "Asha Rao" and me.json()["onboarding_completed"]
    ent = (await c.get("/v1/me/entitlement", headers=headers)).json()
    assert ent["level"] == "trial" and ent["live_controls"]


async def test_line_setup_and_verification_call(app_env):
    c = app_env.client
    headers = await sign_in(c)
    line = await setup_line(c, headers)
    assert line["assistant_number"] == "+918047491899"
    assert line["activation_codes"][0]["code"] == "**67*+918047491899#"
    assert line["status"] == "pending"
    resp = await c.post(f"/v1/lines/{line['id']}/verify", headers=headers)
    assert resp.status_code == 202
    placed = app_env.provider.placed[-1]
    assert placed["to"] == "+919876543210" and placed["from"] == "+918047491899" and placed["purpose"] == "verify"

    async with bus.subscribe(user_topic((await c.get("/v1/me", headers=headers)).json()["id"])) as q:
        # The phone declined; the carrier forwarded the test call back to the assistant number.
        twiml = await c.post("/telephony/twilio/inbound", data={"CallSid": "CA9", "From": "+918047491899", "To": "+918047491899"})
        assert "set up" in twiml.text
        event = await asyncio.wait_for(q.get(), 1)
        assert event["type"] == "line.verified"
    assert (await c.get("/v1/lines/current", headers=headers)).json()["status"] == "verified"


async def test_inbound_call_routes_to_agent_with_hint_and_contacts(app_env):
    c = app_env.client
    headers = await sign_in(c)
    await setup_line(c, headers)
    await c.post("/v1/contacts/sync", json={"contacts": [{"name": "Ravi (landlord)", "numbers": ["09811122233"]}]}, headers=headers)

    resp = await c.post("/telephony/twilio/inbound", data={"CallSid": "CA1", "From": "+919811122233", "To": "+918047491899"})
    assert resp.status_code == 200 and "<Stream" in resp.text and "/telephony/media/call_" in resp.text
    async with sessionmaker()() as s:
        call = await s.scalar(select(Call).where(Call.provider_call_id == "CA1"))
        assert call.caller_known_name == "Ravi (landlord)" and call.mode == "screen"
        line = await s.scalar(select(Line))
        assert line.status == "verified"  # a real forwarded call proves forwarding works

    # Carrier shows the user's own number on a forwarded call: the phone's hint gives the real caller.
    await c.post("/v1/screening/hints", json={"caller_number": "+917000000001"}, headers=headers)
    await c.post("/telephony/twilio/inbound", data={"CallSid": "CA2", "From": "+919876543210", "To": "+918047491899"})
    # The user calling their own assistant with no hint: demo mode.
    await c.post("/telephony/twilio/inbound", data={"CallSid": "CA3", "From": "+919876543210", "To": "+918047491899"})
    async with sessionmaker()() as s:
        hinted = await s.scalar(select(Call).where(Call.provider_call_id == "CA2"))
        demo = await s.scalar(select(Call).where(Call.provider_call_id == "CA3"))
    assert hinted.from_number == "+917000000001" and hinted.mode == "screen"
    assert demo.mode == "demo"

    unknown = await c.post("/telephony/twilio/inbound", data={"CallSid": "CA4", "From": "+917000000002", "To": "+918000000000"})
    assert "not in service" in unknown.text
    # Our own number calling in (a take-over the user didn't answer): never answer ourselves.
    loop = await c.post("/telephony/twilio/inbound", data={"CallSid": "CA5", "From": "+918047491899", "To": "+918047491899"})
    assert "not able to join" in loop.text


async def _live_call(app_env) -> tuple[dict, str]:
    c = app_env.client
    headers = await sign_in(c)
    await setup_line(c, headers)
    await c.post("/telephony/twilio/inbound", data={"CallSid": "CA1", "From": "+917011112222", "To": "+918047491899"})
    async with sessionmaker()() as s:
        call = await s.scalar(select(Call).where(Call.provider_call_id == "CA1"))
    await call_service.set_state(call.id, "live", answered_at=utcnow())
    return headers, call.id


async def test_live_transcript_intent_and_summary(app_env):
    c = app_env.client
    headers, call_id = await _live_call(app_env)
    await call_service.append_transcript(call_id, "assistant", "Hi, who's calling?")
    await call_service.append_transcript(call_id, "caller", "Rahul from Blue Dart, parcel at your gate, need OTP")
    app_env.llm.queue_structured(
        "LiveIntent",
        LiveIntent(caller_name="Rahul", organisation="Blue Dart", category="delivery", reason="Parcel at gate, needs OTP", urgency="high", suggested_replies=["Leave it with security"]),
    )
    tracker = LiveIntentTracker(call_id, "Asha Rao", debounce=0.01)
    tracker.caller_spoke()
    await asyncio.sleep(0.2)
    live = (await c.get(f"/v1/calls/{call_id}", headers=headers)).json()
    assert live["title"] == "Rahul · Blue Dart" and live["suggested_replies"] == ["Leave it with security"]
    assert any(d.get("type") == "call.live" for _, d in app_env.push.sent)

    async with bus.subscribe(call_topic(call_id)) as q:
        r = await c.post(f"/v1/calls/{call_id}/say", json={"text": "Leave it with security"}, headers=headers)
        assert r.status_code == 202
        assert (await asyncio.wait_for(q.get(), 1)) == {"type": "say", "text": "Leave it with security"}
        await c.post(f"/v1/calls/{call_id}/takeover", headers=headers)
        assert (await asyncio.wait_for(q.get(), 1))["type"] == "takeover"

    await call_service.finish_call(call_id, "completed")
    app_env.llm.queue_structured(
        "CallInsights",
        CallInsights(
            caller_name="Rahul",
            organisation="Blue Dart",
            category="delivery",
            reason="Parcel delivery",
            summary="Rahul from Blue Dart was at the gate with a parcel. He left it with security.",
            actions=[SuggestedAction(type="save_contact", title="Save Rahul (Blue Dart)", contact_name="Rahul Blue Dart")],
        ),
    )
    await summarize_call(call_id)
    detail = (await c.get(f"/v1/calls/{call_id}", headers=headers)).json()
    assert detail["state"] == "summarized" and "security" in detail["summary"]
    assert detail["actions"][0]["type"] == "save_contact" and detail["actions"][0]["payload"]["number"] == "+917011112222"
    assert [t["speaker"] for t in detail["transcript"]] == ["assistant", "caller"]
    page = (await c.get("/v1/calls", params={"q": "blue dart"}, headers=headers)).json()
    assert len(page["items"]) == 1 and page["items"][0]["category_label"] == "Delivery or courier"
    assert (await c.post(f"/v1/calls/{call_id}/say", json={"text": "hi"}, headers=headers)).status_code == 409
    await c.delete(f"/v1/calls/{call_id}", headers=headers)
    assert (await c.get(f"/v1/calls/{call_id}", headers=headers)).status_code == 404


async def test_live_controls_need_pro_after_trial(app_env):
    c = app_env.client
    headers, call_id = await _live_call(app_env)
    async with sessionmaker()() as s:
        user = await s.scalar(select(User))
        user.trial_ends_at = utcnow() - timedelta(days=1)
        await s.commit()
    r = await c.post(f"/v1/calls/{call_id}/say", json={"text": "hello"}, headers=headers)
    assert r.status_code == 402
    ent = (await c.get("/v1/me/entitlement", headers=headers)).json()
    assert ent["level"] == "free" and ent["calls_left_this_month"] == 14


async def test_assistant_chat_schedules_a_call(app_env):
    c = app_env.client
    headers = await sign_in(c)
    await setup_line(c, headers)
    app_env.llm.queue_create(
        [
            {"type": "text", "text": "On it."},
            {
                "type": "tool_use",
                "id": "tu_1",
                "name": "schedule_call",
                "input": {"to_number": "080 4000 1234", "to_name": "Apollo Clinic", "goal": "Book a general checkup for Asha tomorrow morning", "when": None},
            },
            {"type": "tool_use", "id": "tu_2", "name": "set_reminder", "input": {"title": "Checkup", "due_at": "2026-11-17T10:00:00+05:30"}},
        ],
        stop_reason="tool_use",
    )
    app_env.llm.queue_create([{"type": "text", "text": "I'm calling Apollo Clinic now and set a reminder for 10 AM."}])
    resp = await c.post("/v1/assistant/chat", json={"text": "Call Apollo clinic 080 4000 1234 and book a checkup"}, headers=headers)
    body = resp.json()
    assert "Apollo" in body["reply"]
    kinds = [a["type"] for a in body["client_actions"]]
    assert kinds == ["outbound_scheduled", "reminder"]
    tasks = (await c.get("/v1/outbound", headers=headers)).json()
    assert tasks[0]["to_number"] == "+918040001234" and tasks[0]["state"] == "scheduled"
    second_request = app_env.llm.calls[-1]["messages"]
    assert second_request[-1]["content"][0]["type"] == "tool_result"
    history = (await c.get("/v1/assistant/chat", headers=headers)).json()
    assert [m["role"] for m in history] == ["user", "assistant", "assistant"]

    await dial(tasks[0]["id"])
    assert app_env.provider.placed[-1]["purpose"] == "outbound" and app_env.provider.placed[-1]["to"] == "+918040001234"
    async with sessionmaker()() as s:
        task = await s.get(OutboundTask, tasks[0]["id"])
        call = await s.get(Call, task.call_id)
    assert task.state == "dialing" and call.provider_call_id == "CA1" and call.mode == "outbound"


async def test_exotel_flow_endpoints(app_env):
    c = app_env.client
    headers = await sign_in(c)
    await setup_line(c, headers)
    r = await c.get("/telephony/exotel/hook-secret/voicebot", params={"CallSid": "EX1"})
    assert r.json()["url"].startswith("wss://api.example.com/telephony/media/exotel-new/")
    assert (await c.get("/telephony/exotel/wrong/voicebot")).status_code == 403
    async with sessionmaker()() as s:
        decision = await call_service.route_inbound(s, provider="exotel", provider_call_id="EX1", from_raw="07011112222", to_raw="08047491899")
    assert decision.kind == "agent"
    assert (await c.get("/telephony/exotel/hook-secret/passthru", params={"CallSid": "EX1"})).status_code == 302
    await call_service.set_state(decision.call_id, "taken_over", takeover_requested=True)
    assert (await c.get("/telephony/exotel/hook-secret/passthru", params={"CallSid": "EX1"})).status_code == 200
    connect = (await c.get("/telephony/exotel/hook-secret/connect", params={"CallSid": "EX1"})).json()
    assert connect["destination"]["numbers"] == ["+919876543210"] and connect["outgoing_phone_number"] == "+918047491899"


async def test_settings_rules_and_policy(app_env):
    c = app_env.client
    headers = await sign_in(c)
    await setup_line(c, headers)
    a = (await c.patch("/v1/assistant", json={"voice": "shubh", "languages": ["hi-IN", "xx"], "snooze_minutes": 30, "pack_ids": ["banks", "nope"]}, headers=headers)).json()
    assert a["voice"] == "shubh" and a["languages"] == ["hi-IN"] and a["pack_ids"] == ["banks"] and a["snooze_until"]
    assert (await c.patch("/v1/assistant", json={"voice": "robot"}, headers=headers)).status_code == 400
    rules = await c.put(
        "/v1/rules",
        json=[
            {"match_type": "category", "match_value": "sales", "action": "decline"},
            {"match_type": "number", "match_value": "09811122233", "action": "ring_me"},
            {"match_type": "category", "match_value": "unknown-cat", "action": "decline"},
        ],
        headers=headers,
    )
    assert len(rules.json()) == 2
    policy = (await c.get("/v1/screening/policy", headers=headers)).json()
    assert "+919811122233" in policy["always_ring"] and "+918047491899" in policy["always_ring"]
    options = (await c.get("/v1/assistant/options", headers=headers)).json()
    assert options["packs"] and "delivery" in options["categories"]
