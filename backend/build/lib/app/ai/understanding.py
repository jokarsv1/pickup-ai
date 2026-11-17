"""Call understanding: live intent while the call runs, insights after it ends."""

import asyncio

from loguru import logger

from app.ai.llm import LLMError, get_llm
from app.ai.prompts import INSIGHTS_SYSTEM, INTENT_SYSTEM, first_name, render_transcript
from app.ai.schemas import CallInsights, LiveIntent
from app.db import sessionmaker
from app.models import Call, User
from app.services import calls as call_service


class LiveIntentTracker:
    """Re-reads the transcript after each caller turn (debounced) and updates the phone.

    Runs beside the voice pipeline, so it never adds latency to what the caller hears.
    """

    def __init__(self, call_id: str, owner_name: str, debounce: float = 1.2) -> None:
        self._call_id = call_id
        self._owner_first = first_name(owner_name)
        self._debounce = debounce
        self._task: asyncio.Task | None = None
        self._dirty = False

    def caller_spoke(self) -> None:
        self._dirty = True
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while self._dirty:
            self._dirty = False
            await asyncio.sleep(self._debounce)
            try:
                async with sessionmaker()() as session:
                    pairs = await call_service.transcript_pairs(session, self._call_id)
                if not any(speaker == "caller" for speaker, _ in pairs):
                    continue
                intent = await get_llm().structured(
                    system=INTENT_SYSTEM,
                    prompt="Live transcript so far:\n\n" + render_transcript(pairs, self._owner_first),
                    schema=LiveIntent,
                    effort="low",
                    max_tokens=1500,
                )
                await call_service.apply_intent(self._call_id, intent)
            except LLMError as exc:
                logger.warning(f"Live intent skipped: {exc}")
            except Exception:
                logger.exception("Live intent failed")

    async def close(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()


async def summarize_call(call_id: str, attempts: int = 3) -> None:
    """Post-call job: insights, actions and the summary notification. Retries with backoff."""
    for attempt in range(1, attempts + 1):
        try:
            async with sessionmaker()() as session:
                call = await session.get(Call, call_id)
                if call is None or call.mode == "demo":
                    return
                user = await session.get(User, call.user_id)
                pairs = await call_service.transcript_pairs(session, call_id)
            if not pairs or not any(speaker == "caller" for speaker, _ in pairs):
                await call_service.set_state(call_id, "summarized", summary="The caller hung up before saying anything.", reason="Hung up without speaking")
                await call_service.notify(call.user_id, {"type": "summary", "call_id": call_id, "summary": "The caller hung up before saying anything.", "actions": []})
                return
            owner_first = first_name(user.name if user else "")
            context = f"Owner: {user.name if user else 'the user'}. Call started {call.started_at.isoformat()}. Caller number: {call.from_number or 'hidden'}."
            if call.direction == "outbound":
                context += " This was an outbound call the assistant made for the owner."
            insights = await get_llm().structured(
                system=INSIGHTS_SYSTEM,
                prompt=f"{context}\n\nTranscript:\n{render_transcript(pairs, owner_first)}",
                schema=CallInsights,
                effort="medium",
                max_tokens=3000,
            )
            await call_service.apply_insights(call_id, insights)
            if call.direction == "outbound":
                from app.services.outbound import complete_from_summary

                await complete_from_summary(call_id)
            return
        except LLMError as exc:
            logger.warning(f"Summary attempt {attempt} failed: {exc}")
        except Exception:
            logger.exception(f"Summary attempt {attempt} crashed")
        await asyncio.sleep(2**attempt)
    await call_service.set_state(call_id, "failed")
