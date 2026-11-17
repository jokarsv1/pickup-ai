"""Talk to the voice agent's brain in your terminal, as if you were the caller.

Uses the exact prompt and model of a live call, without telephony or speech services, so you can
tune instructions with only an Anthropic key:

    ANTHROPIC_API_KEY=... python -m scripts.chat_with_agent --owner "Asha Rao" --packs deliveries,scam_shield

Commands while chatting:
    /say <text>   send a note from the owner ("tell them to leave it at the door")
    /quit         stop
"""

import argparse
import sys

import anthropic

from app.ai.prompts import CallContext, first_name, greeting_for, voice_system_prompt
from app.config import get_settings

TOOLS = [
    {"name": "end_call", "description": "Hang up after saying goodbye.", "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
    {"name": "connect_owner", "description": "Transfer the caller to the owner.", "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="Asha Rao")
    parser.add_argument("--languages", default="en-IN,hi-IN")
    parser.add_argument("--packs", default="deliveries,sales_calls,banks,scam_shield")
    parser.add_argument("--instructions", default="")
    parser.add_argument("--delivery-note", default=None)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("Set ANTHROPIC_API_KEY first.", file=sys.stderr)
        return 2
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    ctx = CallContext(
        mode="screen",
        owner_name=args.owner,
        assistant_name="Pickup",
        languages=[c.strip() for c in args.languages.split(",") if c.strip()],
        caller_number="+919811122233",
        pack_ids=[p.strip() for p in args.packs.split(",") if p.strip()],
        instructions=args.instructions,
        delivery_note=args.delivery_note,
    )
    system = voice_system_prompt(ctx)
    greeting = greeting_for(ctx)
    messages: list[dict] = [{"role": "user", "content": "(The call connects.)"}, {"role": "assistant", "content": greeting}]
    print(f"Pickup: {greeting}")
    while True:
        try:
            line = input("You (caller): ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if not line:
            continue
        if line == "/quit":
            return 0
        if line.startswith("/say "):
            line = f"[{first_name(args.owner)} says: {line[5:]}] Relay this to the caller now, in their language."
        messages.append({"role": "user", "content": line})
        reply = client.messages.create(
            model=settings.claude_model,
            max_tokens=600,
            system=system,
            messages=messages,
            tools=TOOLS,
            output_config={"effort": settings.claude_live_effort},
        )
        messages.append({"role": "assistant", "content": [b.model_dump(mode="json", exclude_none=True) for b in reply.content]})
        text = " ".join(b.text for b in reply.content if b.type == "text").strip()
        if text:
            print(f"Pickup: {text}")
        tool = next((b for b in reply.content if b.type == "tool_use"), None)
        if tool is not None:
            print(f"(Pickup used {tool.name}: {tool.input.get('reason', '')})")
            return 0


if __name__ == "__main__":
    sys.exit(main())
