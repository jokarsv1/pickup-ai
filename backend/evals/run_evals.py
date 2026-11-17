"""Conversation evals for the voice agent's brain.

Claude plays realistic callers (Hinglish delivery agents, KYC scammers, recruiters...) against the
exact system prompt the live agent uses, then a grader scores each conversation against the
scenario's checks. Run before every prompt or model change:

    ANTHROPIC_API_KEY=... python -m evals.run_evals                # all scenarios
    ANTHROPIC_API_KEY=... python -m evals.run_evals kyc_scam -v     # one scenario, print transcript

This uses text, not audio: it tests what the agent says, not speech recognition or voices.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

from app.ai.llm import fallback_args
from app.ai.prompts import CallContext, greeting_for, voice_system_prompt
from app.config import get_settings

MAX_TURNS = 10
# The caller simulator and the grader stay on a stronger model than the agent under test.
SIM_MODEL = os.environ.get("EVAL_SIM_MODEL", "claude-opus-5-5")

AGENT_TOOLS = [
    {
        "name": "end_call",
        "description": "Hang up after you have said goodbye.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
    },
    {
        "name": "connect_owner",
        "description": "Transfer the caller to the owner directly. Only for genuine emergencies or when instructed.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
    },
]


class CheckResult(BaseModel):
    check: str
    passed: bool
    reason: str


class Grade(BaseModel):
    results: list[CheckResult]
    naturalness: int  # 1-5: short, human-sounding turns suited to a phone call


def context_for(scenario: dict) -> CallContext:
    return CallContext(
        mode="screen",
        owner_name=scenario["owner_name"],
        assistant_name="Pickup",
        languages=scenario.get("languages", ["en-IN"]),
        caller_number="+919811122233",
        pack_ids=scenario.get("pack_ids", []),
        instructions=scenario.get("instructions", ""),
        delivery_note=scenario.get("delivery_note"),
        urgent_passthrough=True,
    )


def text_of(content) -> str:
    return " ".join(block.text for block in content if getattr(block, "type", "") == "text").strip()


def run_scenario(client: anthropic.Anthropic, model: str, scenario: dict, verbose: bool) -> dict:
    ctx = context_for(scenario)
    system = voice_system_prompt(ctx)
    greeting = greeting_for(ctx)
    transcript: list[tuple[str, str]] = [("assistant", greeting)]
    messages: list[dict] = [{"role": "user", "content": "(The call connects.)"}, {"role": "assistant", "content": greeting}]
    tool_used = None

    for _ in range(MAX_TURNS):
        caller_view = "\n".join(f"{'You' if s == 'caller' else 'Assistant'}: {t}" for s, t in transcript)
        caller = client.messages.create(
            model=SIM_MODEL,
            max_tokens=300,
            system=scenario["caller"]
            + " You are on a phone call with an AI assistant answering for the person you called. Reply with your next spoken line only. "
            "If you are done or would hang up, reply exactly [HANGS UP].",
            messages=[{"role": "user", "content": f"Conversation so far:\n{caller_view}\n\nYour next line:"}],
            output_config={"effort": "low"},
        )
        caller_line = text_of(caller.content)
        if not caller_line or "[HANGS UP]" in caller_line:
            break
        transcript.append(("caller", caller_line))
        messages.append({"role": "user", "content": caller_line})

        reply = client.beta.messages.create(
            model=model,
            max_tokens=600,
            system=system,
            messages=messages,
            tools=AGENT_TOOLS,
            output_config={"effort": get_settings().claude_live_effort},
            **fallback_args(model),
        )
        content = [block.model_dump(mode="json", exclude_none=True) for block in reply.content]
        messages.append({"role": "assistant", "content": content})
        spoken = text_of(reply.content)
        if spoken:
            transcript.append(("assistant", spoken))
        tool_calls = [b for b in reply.content if getattr(b, "type", "") == "tool_use"]
        if tool_calls:
            tool_used = tool_calls[0].name
            break

    rendered = "\n".join(f"{'Caller' if s == 'caller' else 'Assistant'}: {t}" for s, t in transcript)
    if tool_used:
        rendered += f"\n(The assistant called the {tool_used} tool.)"
    checks = "\n".join(f"- {c}" for c in scenario["checks"])
    grade = client.messages.parse(
        model=SIM_MODEL,
        max_tokens=2000,
        system="You grade phone conversations handled by an AI call assistant. Be strict and literal. Judge only from the transcript.",
        messages=[{"role": "user", "content": f"Transcript:\n{rendered}\n\nChecks:\n{checks}\n\nGrade each check, then rate naturalness 1-5."}],
        output_format=Grade,
        output_config={"effort": "medium"},
    ).parsed_output
    passed = sum(r.passed for r in grade.results)
    if verbose:
        print(f"\n=== {scenario['id']} ===\n{rendered}\n")
        for r in grade.results:
            print(f"  [{'PASS' if r.passed else 'FAIL'}] {r.check}: {r.reason}")
    return {"id": scenario["id"], "passed": passed, "total": len(grade.results), "naturalness": grade.naturalness, "transcript": rendered}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="Scenario ids to run (default: all)")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--out", default="evals/last_run.json")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("Set ANTHROPIC_API_KEY to run evals.", file=sys.stderr)
        return 2
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    scenarios = json.loads((Path(__file__).parent / "scenarios.json").read_text())
    if args.ids:
        scenarios = [s for s in scenarios if s["id"] in args.ids]

    print(f"Assistant model: {settings.claude_model} (effort {settings.claude_live_effort}); caller and grader: {SIM_MODEL}")
    results = [run_scenario(client, settings.claude_model, s, args.verbose) for s in scenarios]
    total = sum(r["total"] for r in results)
    passed = sum(r["passed"] for r in results)
    print(f"\n{'scenario':<24}{'checks':>10}{'natural':>10}")
    for r in results:
        print(f"{r['id']:<24}{r['passed']:>5}/{r['total']:<4}{r['naturalness']:>9}/5")
    print(f"{'TOTAL':<24}{passed:>5}/{total:<4}")
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
