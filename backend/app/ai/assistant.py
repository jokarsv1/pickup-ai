"""The in-app assistant: chat or voice notes ("call the clinic tomorrow at 10", "remind me to call
Rahul back", "stop answering bank calls"). Claude with tools, in a manual loop so every turn's
full content (thinking included) is stored and replayed verbatim.
"""

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMError, content_to_dicts, get_llm
from app.db import utcnow
from app.entitlements import entitlement_for
from app.models import AssistantSettings, Call, ChatMessage, OutboundTask, User
from app.phone import normalize, pretty
from app.services.outbound import outbound_problem

IST = ZoneInfo("Asia/Kolkata")
MAX_STEPS = 6
HISTORY = 30

TOOLS: list[dict[str, Any]] = [
    {
        "name": "schedule_call",
        "description": "Have the phone assistant call someone for the user, now or at a set time, with a clear goal.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "to_number": {"type": "string", "description": "Phone number to call"},
                "to_name": {"type": ["string", "null"], "description": "Who is being called, if known"},
                "goal": {"type": "string", "description": "What the call must achieve, with every detail the assistant needs"},
                "when": {"type": ["string", "null"], "description": "ISO-8601 datetime with offset, or null for right now"},
            },
            "required": ["to_number", "to_name", "goal", "when"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_reminder",
        "description": "Add a reminder to the user's phone.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "due_at": {"type": "string", "description": "ISO-8601 datetime with offset"}},
            "required": ["title", "due_at"],
            "additionalProperties": False,
        },
    },
    {
        "name": "save_contact",
        "description": "Save a phone number to the user's contacts.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "number": {"type": "string"}},
            "required": ["name", "number"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recent_calls",
        "description": "Look up calls the assistant handled recently, newest first.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}, "search": {"type": ["string", "null"], "description": "Name, company or topic"}},
            "required": ["limit", "search"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_instructions",
        "description": "Change how the phone assistant handles calls, by adding to or replacing the user's custom instructions.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "mode": {"type": "string", "enum": ["append", "replace"]}},
            "required": ["text", "mode"],
            "additionalProperties": False,
        },
    },
    {
        "name": "snooze_assistant",
        "description": "Stop the assistant from declining calls for a number of minutes (calls ring normally). 0 resumes it.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"minutes": {"type": "integer"}},
            "required": ["minutes"],
            "additionalProperties": False,
        },
    },
]


def system_prompt(user: User) -> str:
    now = datetime.now(IST).strftime("%A %d %B %Y, %H:%M")
    return (
        f"You are Pickup, {user.name or 'the user'}'s personal assistant inside the Pickup app. Pickup answers "
        "their phone calls with an AI voice, and you can act for them with your tools: schedule calls the "
        "assistant makes, set reminders, save contacts, look up recent calls, and change how calls are handled. "
        f"It is {now} India time; resolve relative times like 'tomorrow at 10' to absolute ISO-8601 with +05:30. "
        "Reply in one or two short sentences, in the user's language. Confirm what you did with the key details. "
        "If something essential is missing (who to call, their number), ask for it instead of guessing."
    )


async def _run_tool(session: AsyncSession, user: User, name: str, args: dict[str, Any], client_actions: list[dict]) -> str:
    if name == "schedule_call":
        ent = await entitlement_for(session, user)
        if not ent.outbound_calls:
            return "Outbound calls need Pickup Pro. Tell the user they can upgrade from Settings."
        number = normalize(args.get("to_number"))
        if not number:
            return "That phone number isn't valid. Ask the user for the full number."
        problem = await outbound_problem(session, user.id, number)
        if problem:
            return problem + " Tell the user."
        when = utcnow()
        if args.get("when"):
            try:
                when = datetime.fromisoformat(args["when"])
                if when.tzinfo is None:
                    when = when.replace(tzinfo=IST)
            except ValueError:
                return "The time couldn't be understood. Ask the user when to call."
        if when < utcnow() - timedelta(minutes=1):
            return "That time is in the past. Ask the user for a future time."
        task = OutboundTask(user_id=user.id, to_number=number, to_name=args.get("to_name"), goal=args["goal"], scheduled_at=when)
        session.add(task)
        await session.flush()
        client_actions.append({"type": "outbound_scheduled", "task_id": task.id, "to": pretty(number), "at": when.isoformat()})
        return f"Scheduled call {task.id} to {pretty(number)} at {when.astimezone(IST).strftime('%d %b %H:%M')} IST."
    if name == "set_reminder":
        client_actions.append({"type": "reminder", "title": args["title"], "due_at": args["due_at"]})
        return "Reminder will be added on the phone."
    if name == "save_contact":
        number = normalize(args.get("number"))
        if not number:
            return "That phone number isn't valid."
        client_actions.append({"type": "save_contact", "name": args["name"], "number": number})
        return "The phone will open the save-contact screen."
    if name == "recent_calls":
        limit = max(1, min(int(args.get("limit") or 5), 20))
        q = select(Call).where(Call.user_id == user.id, Call.deleted.is_(False)).order_by(Call.started_at.desc()).limit(limit)
        rows = (await session.scalars(q)).all()
        search = (args.get("search") or "").lower()
        out = []
        for call in rows:
            text = " ".join(filter(None, [call.caller_name, call.caller_org, call.caller_known_name, call.summary, call.reason])).lower()
            if search and search not in text:
                continue
            out.append(
                {
                    "when": call.started_at.astimezone(IST).strftime("%d %b %H:%M"),
                    "who": call.caller_known_name or call.caller_name or pretty(call.from_number),
                    "org": call.caller_org,
                    "number": call.from_number,
                    "summary": call.summary or call.reason,
                }
            )
        return json.dumps(out) if out else "No matching calls."
    if name == "update_instructions":
        prefs = await session.get(AssistantSettings, user.id)
        if prefs is None:
            prefs = AssistantSettings(user_id=user.id)
            session.add(prefs)
        text = args["text"].strip()
        prefs.instructions = text if args.get("mode") == "replace" else (f"{prefs.instructions}\n{text}".strip() if prefs.instructions else text)
        client_actions.append({"type": "settings_changed"})
        return "Instructions updated."
    if name == "snooze_assistant":
        prefs = await session.get(AssistantSettings, user.id)
        if prefs is None:
            prefs = AssistantSettings(user_id=user.id)
            session.add(prefs)
        minutes = max(0, min(int(args.get("minutes") or 0), 24 * 60))
        prefs.snooze_until = utcnow() + timedelta(minutes=minutes) if minutes else None
        client_actions.append({"type": "snooze", "until": prefs.snooze_until.isoformat() if prefs.snooze_until else None})
        return f"Snoozed for {minutes} minutes." if minutes else "Assistant resumed."
    return f"Unknown tool {name}"


async def chat(session: AsyncSession, user: User, text: str) -> tuple[str, list[dict]]:
    """Run one user message through the assistant. Returns (reply text, client actions)."""
    history = (
        await session.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id).order_by(ChatMessage.id.desc()).limit(HISTORY))
    ).all()
    history = list(reversed(history))
    # Start the replay window on a plain user message so tool_use/tool_result pairs stay intact.
    while history and not (history[0].role == "user" and history[0].text):
        history.pop(0)
    messages: list[dict[str, Any]] = [{"role": "user" if m.role in ("user", "tool") else "assistant", "content": m.content} for m in history]
    user_msg = ChatMessage(user_id=user.id, role="user", text=text, content=[{"type": "text", "text": text}])
    session.add(user_msg)
    messages.append({"role": "user", "content": user_msg.content})

    client_actions: list[dict] = []
    reply = ""
    last_assistant: ChatMessage | None = None
    for _ in range(MAX_STEPS):
        try:
            response = await get_llm().create(system=system_prompt(user), messages=messages, tools=TOOLS, effort="medium", max_tokens=4000)
        except LLMError as exc:
            logger.warning(f"Assistant chat failed: {exc}")
            reply = "Sorry, I can't do that right now. Please try again in a moment."
            break
        content = content_to_dicts(response.content)
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        last_assistant = ChatMessage(user_id=user.id, role="assistant", text=" ".join(t for t in texts if t).strip(), content=content)
        session.add(last_assistant)
        messages.append({"role": "assistant", "content": content})
        if response.stop_reason == "refusal":
            reply = "Sorry, I can't help with that."
            break
        if response.stop_reason == "pause_turn":
            continue
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            reply = last_assistant.text
            break
        results = []
        for block in tool_uses:
            try:
                result = await _run_tool(session, user, block["name"], dict(block.get("input") or {}), client_actions)
                results.append({"type": "tool_result", "tool_use_id": block["id"], "content": result})
            except Exception as exc:
                logger.exception("Tool failed")
                results.append({"type": "tool_result", "tool_use_id": block["id"], "content": f"Error: {exc}", "is_error": True})
        session.add(ChatMessage(user_id=user.id, role="tool", text="", content=results))
        messages.append({"role": "user", "content": results})
    reply = reply or "Done."
    if last_assistant is None:
        # Nothing reached the model: keep the history valid (no dangling user turn) and show the error.
        await session.delete(user_msg)
        await session.commit()
        return reply, client_actions
    if not last_assistant.text:
        last_assistant.text = reply
    last_assistant.client_actions = client_actions
    await session.commit()
    return reply, client_actions
