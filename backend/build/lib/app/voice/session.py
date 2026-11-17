"""One live phone call, end to end.

Pipeline:  phone audio -> VAD + Smart Turn -> speech-to-text -> Claude -> text-to-speech -> phone audio
Beside it: transcript + live intent go to the user's phone; the user's commands (say this,
take over, end) come back on the call's control topic.
"""

import asyncio
import contextlib
from typing import Any

from fastapi import WebSocket
from loguru import logger
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, FunctionCallResultProperties, LLMMessagesAppendFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner
from sqlalchemy import select

from app.ai.prompts import CallContext, first_name, greeting_for, voice_system_prompt
from app.ai.understanding import LiveIntentTracker, summarize_call
from app.config import get_settings
from app.db import sessionmaker, utcnow
from app.entitlements import entitlement_for
from app.events import bus, call_topic
from app.models import AssistantSettings, Call, Line, OutboundTask, Rule, User
from app.packs import CATEGORIES
from app.services import calls as call_service
from app.storage import pcm_to_wav, save_recording
from app.telephony.registry import get_provider
from app.voice.services import make_llm, make_serializer, make_stt, make_tts, missing_keys

SAMPLE_RATE = 8000  # narrowband telephone audio
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def rules_to_text(rules: list[Rule], owner_first: str) -> list[str]:
    lines = []
    for rule in rules:
        target = CATEGORIES.get(rule.match_value, rule.match_value) if rule.match_type == "category" else f"the number {rule.match_value}"
        if rule.action == "decline":
            lines.append(f"Callers about {target}: politely decline and end the call quickly.")
        elif rule.action == "connect":
            lines.append(f"Callers about {target}: {owner_first} wants to talk to them; offer to connect them (connect_owner).")
        elif rule.action == "ring_me":
            lines.append(f"Callers about {target}: take their details and tell them {owner_first} will call back soon.")
        if rule.note:
            lines.append(f"Note for {target}: {rule.note}")
    return lines


async def load_context(call_id: str) -> tuple[Call, User, Line | None, CallContext, AssistantSettings, bool]:
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            raise LookupError(call_id)
        user = await session.get(User, call.user_id)
        assert user is not None
        prefs = await session.get(AssistantSettings, user.id) or AssistantSettings(user_id=user.id)
        line = await session.get(Line, call.line_id) if call.line_id else None
        rules = (await session.scalars(select(Rule).where(Rule.user_id == user.id))).all()
        task = await session.get(OutboundTask, call.outbound_task_id) if call.outbound_task_id else None
        ent = await entitlement_for(session, user)
        rep = await call_service.reputation_note(session, call.from_number)
    owner = user.name or "the user"
    ctx = CallContext(
        mode=call.mode,
        owner_name=owner,
        assistant_name=prefs.assistant_name or "Pickup",
        languages=list(prefs.languages or [user.language]),
        caller_number=call.from_number if call.direction == "inbound" else call.to_number,
        caller_known_name=call.caller_known_name,
        reputation_note=rep,
        pack_ids=list(prefs.pack_ids or []),
        instructions=prefs.instructions or "",
        delivery_note=prefs.delivery_note,
        rules_text=rules_to_text(list(rules), first_name(owner)),
        urgent_passthrough=prefs.urgent_passthrough and ent.live_controls,
        record_calls=prefs.record_calls,
        outbound_goal=task.goal if task else None,
        outbound_to_name=task.to_name if task else None,
    )
    return call, user, line, ctx, prefs, ent.live_controls


class VoiceSession:
    def __init__(self, websocket: WebSocket, call_id: str, transport_type: str, call_data: Any) -> None:
        self.ws = websocket
        self.call_id = call_id
        self.transport_type = transport_type
        self.call_data = call_data
        self.worker: PipelineWorker | None = None
        self._audio: tuple[bytes, int, int] | None = None
        self._takeover_started = False
        self._ending = False
        self.end_reason = "hangup"

    async def run(self) -> None:
        call, user, line, ctx, prefs, live_controls = await load_context(self.call_id)
        self.call, self.user, self.line, self.ctx, self.prefs = call, user, line, ctx, prefs
        self.owner_first = first_name(ctx.owner_name)
        self.live_controls = live_controls
        tracker = LiveIntentTracker(self.call_id, ctx.owner_name) if call.mode in ("screen", "message_only", "outbound") else None

        transport = FastAPIWebsocketTransport(
            websocket=self.ws,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                serializer=make_serializer(self.transport_type, self.call_data),
                session_timeout=get_settings().max_call_seconds,
            ),
        )
        greeting = greeting_for(ctx, prefs.greeting if call.mode == "screen" else None)
        tools = ToolsSchema(standard_tools=self._tool_schemas())
        llm = make_llm(voice_system_prompt(ctx))
        llm.register_function("end_call", self._end_call)
        if ctx.urgent_passthrough:
            llm.register_function("connect_owner", self._connect_owner)
        context = LLMContext(tools=tools)
        aggregators = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()))
        recorder = AudioBufferProcessor(num_channels=1)

        pipeline = Pipeline(
            [
                transport.input(),
                make_stt(ctx.languages),
                aggregators.user(),
                llm,
                make_tts(prefs.voice, ctx.languages),
                transport.output(),
                recorder,
                aggregators.assistant(),
            ]
        )
        self.worker = PipelineWorker(
            pipeline,
            params=PipelineParams(audio_in_sample_rate=SAMPLE_RATE, audio_out_sample_rate=SAMPLE_RATE, enable_metrics=True),
            enable_rtvi=False,
            idle_timeout_secs=45,
        )

        @transport.event_handler("on_client_connected")
        async def _connected(_transport, _ws):
            await call_service.set_state(self.call_id, "live", answered_at=utcnow())
            if prefs.record_calls and call.mode != "demo":
                await recorder.start_recording()
            await self.worker.queue_frames([TTSSpeakFrame(greeting)])

        @transport.event_handler("on_client_disconnected")
        async def _disconnected(_transport, _ws):
            await self.worker.cancel()

        @transport.event_handler("on_session_timeout")
        async def _timeout(_transport, _ws):
            self.end_reason = "time_limit"
            await self.worker.queue_frames(
                [TTSSpeakFrame(f"I have to go now. I'll pass your message to {self.owner_first}. Goodbye!", append_to_context=False), EndFrame()]
            )

        @aggregators.user().event_handler("on_user_turn_message_added")
        async def _caller_turn(_aggregator, message):
            await call_service.append_transcript(self.call_id, "caller", message.content)
            if tracker:
                tracker.caller_spoke()

        @aggregators.assistant().event_handler("on_assistant_turn_stopped")
        async def _assistant_turn(_aggregator, message):
            if message.content:
                await call_service.append_transcript(self.call_id, "assistant", message.content)

        @recorder.event_handler("on_audio_data")
        async def _audio(_recorder, audio, sample_rate, num_channels):
            self._audio = (audio, sample_rate, num_channels)

        control = asyncio.create_task(self._control_loop())
        try:
            await WorkerRunner(handle_sigint=False).run(self.worker)
        finally:
            control.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await control
            if tracker:
                await tracker.close()
            with contextlib.suppress(Exception):
                await recorder.stop_recording()
            await self._finish()

    def _tool_schemas(self) -> list[FunctionSchema]:
        tools = [
            FunctionSchema(
                name="end_call",
                description="Hang up after you have said goodbye. Use when the conversation is complete, the caller is a spammer, or the caller wants to leave.",
                properties={"reason": {"type": "string", "description": "Why the call is ending, in a few words"}},
                required=["reason"],
            )
        ]
        if self.ctx.urgent_passthrough:
            tools.append(
                FunctionSchema(
                    name="connect_owner",
                    description=f"Transfer the caller to {self.owner_first} directly. Only for genuine emergencies or when {self.owner_first}'s instructions say to connect this caller.",
                    properties={"reason": {"type": "string", "description": "Why the caller needs the owner right now"}},
                    required=["reason"],
                )
            )
        return tools

    async def _end_call(self, params: FunctionCallParams) -> None:
        self.end_reason = str(params.arguments.get("reason") or "completed")[:40]
        await params.result_callback({"status": "ending"}, properties=FunctionCallResultProperties(run_llm=False))
        await self._end_soon()

    async def _connect_owner(self, params: FunctionCallParams) -> None:
        await params.result_callback({"status": "connecting"}, properties=FunctionCallResultProperties(run_llm=False))
        _spawn(self.start_takeover(initiator="caller"))

    async def _end_soon(self) -> None:
        if self._ending or self.worker is None:
            return
        self._ending = True
        await self.worker.queue_frame(EndFrame())

    async def _control_loop(self) -> None:
        async with bus.subscribe(call_topic(self.call_id)) as queue:
            while True:
                command = await queue.get()
                kind = command.get("type")
                try:
                    if kind == "say" and command.get("text"):
                        text = str(command["text"])[:300]
                        await call_service.append_transcript(self.call_id, "owner", text)
                        note = f"[{self.owner_first} says: {text}] Relay this to the caller now, in their language."
                        await self.worker.queue_frames([LLMMessagesAppendFrame(messages=[{"role": "user", "content": note}], run_llm=True)])
                    elif kind == "takeover":
                        _spawn(self.start_takeover(initiator="owner"))
                    elif kind == "end":
                        self.end_reason = "ended_by_owner"
                        note = f"[{self.owner_first} asks you to wrap up now: say a short, polite goodbye and end the call.]"
                        await self.worker.queue_frames([LLMMessagesAppendFrame(messages=[{"role": "user", "content": note}], run_llm=True)])
                except Exception:
                    logger.exception(f"Control command {kind} failed")

    async def start_takeover(self, initiator: str) -> None:
        if self._takeover_started or self.line is None or self.worker is None:
            return
        self._takeover_started = True
        self.end_reason = "taken_over"
        await call_service.set_state(self.call_id, "taken_over", takeover_requested=True, taken_over_at=utcnow())
        await call_service.notify(self.user.id, {"type": "takeover.ringing", "call_id": self.call_id, "initiator": initiator}, push=True)
        await self.worker.queue_frames([TTSSpeakFrame(f"Connecting you to {self.owner_first} now. Please hold.", append_to_context=False)])
        await asyncio.sleep(3.5)  # let the sentence finish before the line moves
        provider = get_provider(self.call.provider)
        try:
            handled = await provider.transfer(
                call_id=self.call_id,
                provider_call_id=self.call.provider_call_id or "",
                to_number=self.line.phone_e164,
                caller_id=self.line.assistant_number,
            )
        except Exception:
            logger.exception("Transfer failed")
            self._takeover_started = False
            await call_service.set_state(self.call_id, "live", takeover_requested=False)
            await self.worker.queue_frames(
                [TTSSpeakFrame(f"Sorry, I couldn't connect you. I'll make sure {self.owner_first} gets your message.", append_to_context=False)]
            )
            return
        if not handled:
            await self._end_soon()  # e.g. Exotel: closing the stream hands the call to the flow's Connect applet

    async def _finish(self) -> None:
        recording_key = None
        if self._audio and self.prefs.record_calls and self.call.mode != "demo":
            audio, sample_rate, channels = self._audio
            if audio:
                try:
                    recording_key = await save_recording(self.call_id, pcm_to_wav(audio, sample_rate, channels))
                except Exception:
                    logger.exception("Saving recording failed")
        await call_service.finish_call(self.call_id, self.end_reason, recording_key)
        if self.call.mode != "demo":
            _spawn(summarize_call(self.call_id))


async def run_call(websocket: WebSocket, call_id: str, transport_type: str, call_data: Any) -> None:
    missing = missing_keys()
    if missing:
        logger.error(f"Cannot answer call {call_id}: missing {', '.join(missing)}")
        await call_service.finish_call(call_id, "voice_unavailable")
        return
    await VoiceSession(websocket, call_id, transport_type, call_data).run()


async def run_notice(websocket: WebSocket, transport_type: str, call_data: Any, text: str, languages: list[str] | None = None) -> None:
    """Speak one sentence and hang up (verification calls, loops, unknown numbers)."""
    if missing_keys():
        return
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(audio_out_enabled=True, add_wav_header=False, serializer=make_serializer(transport_type, call_data)),
    )
    tts = make_tts("ritu", languages or ["en-IN"])
    worker = PipelineWorker(
        Pipeline([transport.input(), tts, transport.output()]),
        params=PipelineParams(audio_in_sample_rate=SAMPLE_RATE, audio_out_sample_rate=SAMPLE_RATE),
        enable_rtvi=False,
        idle_timeout_secs=15,
    )

    @transport.event_handler("on_client_connected")
    async def _connected(_transport, _ws):
        await worker.queue_frames([TTSSpeakFrame(text, append_to_context=False), EndFrame()])

    @transport.event_handler("on_client_disconnected")
    async def _disconnected(_transport, _ws):
        await worker.cancel()

    await WorkerRunner(handle_sigint=False).run(worker)
