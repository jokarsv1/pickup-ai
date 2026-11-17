"""Measure the time and money one AI-handled call costs, from the machine this runs on.

    python -m app.tools.latency_probe

Plays a scripted ~2 minute Hinglish call (a recruiter) against the real voice prompt with the
production model settings, then runs the live-intent and post-call summary requests the server
makes, and times Sarvam text-to-speech and speech-to-text. Prints one JSON report.
Spends a few US cents of Anthropic credit and about one rupee of Sarvam credit.
"""

import asyncio
import base64
import json
import statistics
import time

import anthropic
import httpx
from sarvamai import AsyncSarvamAI

from app.ai.prompts import INSIGHTS_SYSTEM, INTENT_SYSTEM, CallContext, greeting_for, render_transcript, voice_system_prompt
from app.ai.schemas import CallInsights, LiveIntent
from app.config import get_settings

CALLER_LINES = [
    "हाँ hello, मैं Rohit बोल रहा हूँ TalentEdge से, एक job opportunity के बारे में call किया था Asha जी के लिए.",
    "Actually एक fintech company है Bangalore में, उन्हें senior product manager चाहिए, Asha जी का profile LinkedIn पे देखा था.",
    "Package around 45 to 50 lakh है, hybrid role है, हफ्ते में तीन दिन office. क्या वो interested होंगी?",
    "ठीक है. आप उन्हें बोल दीजिए कि interview process दो हफ्ते में close करना है, तो जल्दी reply करें.",
    "मेरा number यही है जिससे call कर रहा हूँ, और email है rohit at talentedge dot in.",
    "हाँ और अगर possible हो तो कल शाम छह बजे के बाद call back कर दें, उस time मैं free रहूँगा.",
    "बस इतना ही था. Thank you, have a good day.",
]

# Claude Opus 5.5 list prices, USD per million tokens.
PRICE = {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20}
SARVAM_STT_INR_PER_MIN = 0.49
SARVAM_TTS_INR_PER_1K_CHARS = 3.00
SENTENCE_END = (".", "?", "!", "।")


def tool_defs() -> list[dict]:
    reason = {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    return [
        {"name": "end_call", "description": "Hang up after you have said goodbye.", "input_schema": reason},
        {"name": "connect_owner", "description": "Transfer the caller to Asha directly. Only for genuine emergencies.", "input_schema": reason},
    ]


def usd(usage) -> float:
    u = usage
    return (
        (u.input_tokens or 0) * PRICE["input"]
        + (u.output_tokens or 0) * PRICE["output"]
        + (getattr(u, "cache_creation_input_tokens", 0) or 0) * PRICE["cache_write"]
        + (getattr(u, "cache_read_input_tokens", 0) or 0) * PRICE["cache_read"]
    ) / 1_000_000


def usage_dict(u) -> dict:
    return {
        "input": u.input_tokens,
        "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
        "output": u.output_tokens,
    }


async def rtt(client: httpx.AsyncClient, url: str, headers: dict) -> float:
    times = []
    for _ in range(4):
        t = time.perf_counter()
        await client.get(url, headers=headers)
        times.append(time.perf_counter() - t)
    return round(min(times[1:]) * 1000)  # skip the first (TLS setup)


async def live_turn(client: anthropic.AsyncAnthropic, system: str, messages: list[dict]) -> dict:
    s = get_settings()
    t0 = time.perf_counter()
    first_text = first_sentence = None
    text = ""
    async with client.beta.messages.stream(
        model=s.claude_model,
        max_tokens=600,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
        tools=tool_defs(),
        output_config={"effort": s.claude_live_effort},
    ) as stream:
        async for event in stream:
            if event.type == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta":
                now = time.perf_counter()
                first_text = first_text or now
                text += event.delta.text
                if first_sentence is None and any(text.rstrip().endswith(p) for p in SENTENCE_END):
                    first_sentence = now
        message = await stream.get_final_message()
    done = time.perf_counter()
    spoken = " ".join(b.text for b in message.content if b.type == "text").strip()
    return {
        "message": message,
        "spoken": spoken,
        "ttft_ms": round(((first_text or done) - t0) * 1000),
        "first_sentence_ms": round(((first_sentence or done) - t0) * 1000),
        "total_ms": round((done - t0) * 1000),
        "usage": usage_dict(message.usage),
        "usd": usd(message.usage),
        "ended": any(b.type == "tool_use" for b in message.content),
    }


async def main() -> None:
    s = get_settings()
    claude = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
    sarvam = AsyncSarvamAI(api_subscription_key=s.sarvam_api_key)
    report: dict = {"model": s.claude_model, "effort_live": s.claude_live_effort}

    async with httpx.AsyncClient(timeout=20) as http:
        report["network_ms"] = {
            "anthropic": await rtt(http, "https://api.anthropic.com/v1/models", {"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01"}),
            "sarvam": await rtt(http, "https://api.sarvam.ai/", {}),
        }

    ctx = CallContext("screen", "Asha Rao", "Pickup", ["hi-IN", "en-IN"], "+919812345678", pack_ids=["recruiters", "scam_shield"])
    system = voice_system_prompt(ctx)
    greeting = greeting_for(ctx)
    messages: list[dict] = [{"role": "user", "content": "(The call connects.)"}, {"role": "assistant", "content": greeting}]
    pairs: list[tuple[str, str]] = [("assistant", greeting)]
    turns = []
    for line in CALLER_LINES:
        messages.append({"role": "user", "content": line})
        pairs.append(("caller", line))
        turn = await live_turn(claude, system, messages)
        messages.append({"role": "assistant", "content": [b.model_dump(mode="json", exclude_none=True) for b in turn.pop("message").content]})
        pairs.append(("assistant", turn["spoken"]))
        turns.append(turn)
        if turn["ended"]:
            break

    # Live intent: the server re-reads the transcript after each caller turn (trial and Pro only).
    intents = []
    for i in range(1, len(pairs)):
        if pairs[i][0] != "caller":
            continue
        t = time.perf_counter()
        r = await claude.beta.messages.parse(
            model=s.claude_model, max_tokens=1500, system=INTENT_SYSTEM,
            messages=[{"role": "user", "content": "Live transcript so far:\n\n" + render_transcript(pairs[: i + 1], "Asha")}],
            output_format=LiveIntent, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        intents.append({"ms": round((time.perf_counter() - t) * 1000), "usage": usage_dict(r.usage), "usd": usd(r.usage)})

    # Post-call summary.
    t = time.perf_counter()
    r = await claude.beta.messages.parse(
        model=s.claude_model, max_tokens=3000, system=INSIGHTS_SYSTEM,
        messages=[{"role": "user", "content": "Owner: Asha Rao. Caller number: +91 98123 45678.\n\nTranscript:\n" + render_transcript(pairs, "Asha")}],
        output_format=CallInsights, output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    summary = {"ms": round((time.perf_counter() - t) * 1000), "usage": usage_dict(r.usage), "usd": usd(r.usage),
               "result": r.parsed_output.model_dump() if r.parsed_output else None}

    # Sarvam text-to-speech: time to get the first sentence of each reply (REST; the live call
    # streams over WebSocket, which starts sooner), and total characters spoken.
    tts_ms = []
    spoken_texts = [greeting] + [t["spoken"] for t in turns if t["spoken"]]
    for text in spoken_texts[:5]:
        first = text
        for p in SENTENCE_END:
            if p in first:
                first = first.split(p)[0] + p
        t = time.perf_counter()
        await sarvam.text_to_speech.convert(text=first, target_language_code="hi-IN", speaker="ritu", model=s.sarvam_tts_model, speech_sample_rate=8000)
        tts_ms.append(round((time.perf_counter() - t) * 1000))

    # Sarvam speech-to-text on a caller sentence (REST, whole clip at once: an upper bound for the
    # live stream, where audio arrives while the caller is still talking).
    audio = await sarvam.text_to_speech.convert(text=CALLER_LINES[2], target_language_code="hi-IN", speaker="shubh", model=s.sarvam_tts_model, speech_sample_rate=16000)
    wav = base64.b64decode(audio.audios[0])
    stt_ms = []
    for _ in range(3):
        t = time.perf_counter()
        await sarvam.speech_to_text.transcribe(file=("caller.wav", wav, "audio/wav"), model="saaras:v3", mode="codemix")
        stt_ms.append(round((time.perf_counter() - t) * 1000))

    chars = sum(len(x) for x in spoken_texts)
    caller_secs = sum(len(x) for x in CALLER_LINES) / 14  # ~14 characters a second of speech
    bot_secs = chars / 14
    call_minutes = (caller_secs + bot_secs) / 60
    live_usd = sum(t["usd"] for t in turns)
    report.update(
        turns=[{k: v for k, v in t.items() if k != "spoken"} | {"reply": t["spoken"]} for t in turns],
        latency_ms={
            "claude_first_text_median": statistics.median(t["ttft_ms"] for t in turns),
            "claude_first_sentence_median": statistics.median(t["first_sentence_ms"] for t in turns),
            "claude_first_sentence_max": max(t["first_sentence_ms"] for t in turns),
            "tts_first_sentence_rest_median": statistics.median(tts_ms),
            "stt_rest_clip_median": statistics.median(stt_ms),
            "stt_clip_seconds": round(len(wav) / 32000, 1),
        },
        intents=intents,
        summary=summary,
        cost={
            "estimated_call_minutes": round(call_minutes, 2),
            "claude_live_usd": round(live_usd, 4),
            "claude_intent_usd": round(sum(i["usd"] for i in intents), 4),
            "claude_summary_usd": round(summary["usd"], 4),
            "tts_chars": chars,
            "tts_inr": round(chars / 1000 * SARVAM_TTS_INR_PER_1K_CHARS, 2),
            "stt_inr_per_2min": round(2 * SARVAM_STT_INR_PER_MIN, 2),
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    asyncio.run(main())
