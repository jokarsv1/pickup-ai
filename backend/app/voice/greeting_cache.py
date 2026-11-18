"""The assistant's first words, synthesised before the call connects.

Equal AI's users complain most about silence: "the first 'Hello' comes much later", "callers say
hello, hello". Synthesising the greeting only after the audio stream opens costs a TTS round trip
(plus its connection setup) while the caller hears nothing. Instead, as soon as a forwarded call
is routed to us, we fetch the greeting audio over Sarvam's REST API; the carrier usually takes a
second or more to connect the stream, so the audio is ready when the caller picks up. Greetings
repeat (same owner, same voice), so they're also kept in a small in-memory cache.

Anything going wrong here falls back to normal streaming synthesis.
"""

import asyncio
import base64
from collections import OrderedDict

import httpx
from loguru import logger

from app.config import get_settings

SARVAM_URL = "https://api.sarvam.ai/text-to-speech"
MAX_ENTRIES = 256  # ~50 KB each at 8 kHz: about 12 MB at most

_cache: "OrderedDict[tuple[str, str, str, int], bytes]" = OrderedDict()
_pending: dict[tuple[str, str, str, int], asyncio.Task] = {}


def _key(text: str, voice: str, language: str, sample_rate: int) -> tuple[str, str, str, int]:
    return (text, voice, language, sample_rate)


def enabled() -> bool:
    s = get_settings()
    return s.tts_provider == "sarvam" and bool(s.sarvam_api_key)


async def synthesize(text: str, voice: str, language: str, sample_rate: int) -> bytes | None:
    """16-bit mono PCM for the text, or None."""
    s = get_settings()
    payload = {
        "text": text,
        "target_language_code": language,
        "speaker": voice,
        "speech_sample_rate": sample_rate,
        "model": s.sarvam_tts_model,
        "pace": 1.0,
        "temperature": 0.6,
    }
    headers = {"api-subscription-key": s.sarvam_api_key or "", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.post(SARVAM_URL, json=payload, headers=headers)
    if resp.status_code != 200:
        logger.warning(f"Greeting synthesis failed: {resp.status_code} {resp.text[:200]}")
        return None
    audios = resp.json().get("audios") or []
    if not audios:
        return None
    audio = base64.b64decode(audios[0])
    if len(audio) > 44 and audio.startswith(b"RIFF"):
        audio = audio[44:]  # WAV header
    return audio or None


def _store(key: tuple[str, str, str, int], audio: bytes) -> None:
    _cache[key] = audio
    _cache.move_to_end(key)
    while len(_cache) > MAX_ENTRIES:
        _cache.popitem(last=False)


def prefetch(text: str, voice: str, language: str, sample_rate: int) -> None:
    """Start synthesising in the background (no-op if cached or already running)."""
    if not enabled() or not text:
        return
    key = _key(text, voice, language, sample_rate)
    if key in _cache or key in _pending:
        return

    async def run() -> None:
        try:
            audio = await synthesize(text, voice, language, sample_rate)
            if audio:
                _store(key, audio)
        except Exception as exc:
            logger.warning(f"Greeting prefetch failed: {exc}")
        finally:
            _pending.pop(key, None)

    _pending[key] = asyncio.create_task(run())


async def get(text: str, voice: str, language: str, sample_rate: int, wait: float = 0.8) -> bytes | None:
    """The greeting audio if it's ready (or becomes ready within `wait` seconds), else None."""
    key = _key(text, voice, language, sample_rate)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    task = _pending.get(key)
    if task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=wait)
        except (TimeoutError, asyncio.TimeoutError):
            return None
        except Exception:
            return None
        return _cache.get(key)
    return None


def clear() -> None:
    _cache.clear()
    for task in _pending.values():
        task.cancel()
    _pending.clear()
