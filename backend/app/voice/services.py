"""Factories for the speech and language services used on a live call."""

from loguru import logger
from pipecat.transcriptions.language import Language

from app.config import get_settings

# Voices that exist in Sarvam's bulbul:v3 catalogue (the default India voice stack).
SARVAM_VOICES = {
    "ritu": "Ritu (female)",
    "priya": "Priya (female)",
    "neha": "Neha (female)",
    "kavya": "Kavya (female)",
    "shubh": "Shubh (male)",
    "aditya": "Aditya (male)",
    "rahul": "Rahul (male)",
    "dev": "Dev (male)",
}


class VoiceStackUnavailable(RuntimeError):
    pass


def to_language(code: str | None) -> Language | None:
    if not code:
        return None
    try:
        return Language(code)
    except ValueError:
        return None


def missing_keys() -> list[str]:
    s = get_settings()
    missing = []
    if not s.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if s.stt_provider == "sarvam" and not s.sarvam_api_key:
        missing.append("SARVAM_API_KEY")
    if s.stt_provider == "deepgram" and not s.deepgram_api_key:
        missing.append("DEEPGRAM_API_KEY")
    if s.tts_provider == "sarvam" and not s.sarvam_api_key:
        missing.append("SARVAM_API_KEY")
    if s.tts_provider == "elevenlabs" and not s.elevenlabs_api_key:
        missing.append("ELEVENLABS_API_KEY")
    if s.tts_provider == "cartesia" and not s.cartesia_api_key:
        missing.append("CARTESIA_API_KEY")
    return sorted(set(missing))


def make_stt(languages: list[str]):
    s = get_settings()
    if s.stt_provider == "sarvam":
        from pipecat.services.sarvam.stt import SarvamRealtimeSTTService

        # language=None lets Sarvam detect the language per utterance; codemix keeps
        # English words in Latin script inside Hindi sentences (Hinglish).
        mixed = any(code != "en-IN" for code in languages)
        return SarvamRealtimeSTTService(
            api_key=s.sarvam_api_key or "",
            settings=SarvamRealtimeSTTService.Settings(model=s.sarvam_stt_model, language=None, mode="codemix" if mixed else "transcribe"),
        )
    from pipecat.services.deepgram.stt import DeepgramSTTService

    return DeepgramSTTService(
        api_key=s.deepgram_api_key or "",
        settings=DeepgramSTTService.Settings(model=s.deepgram_model, language="multi", smart_format=True, punctuate=True),
    )


def make_tts(voice: str, languages: list[str]):
    s = get_settings()
    primary = to_language(languages[0] if languages else "en-IN") or Language.EN_IN
    if s.tts_provider == "sarvam":
        from pipecat.services.sarvam.tts import SarvamTTSService

        if voice not in SARVAM_VOICES:
            logger.warning(f"Unknown Sarvam voice {voice!r}; using ritu")
            voice = "ritu"
        return SarvamTTSService(
            api_key=s.sarvam_api_key or "",
            settings=SarvamTTSService.Settings(model=s.sarvam_tts_model, voice=voice, language=primary),
        )
    if s.tts_provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        return ElevenLabsTTSService(
            api_key=s.elevenlabs_api_key or "", settings=ElevenLabsTTSService.Settings(model=s.elevenlabs_model, voice=voice, language=primary)
        )
    from pipecat.services.cartesia.tts import CartesiaTTSService

    return CartesiaTTSService(
        api_key=s.cartesia_api_key or "", settings=CartesiaTTSService.Settings(model=s.cartesia_model, voice=voice, language=primary)
    )


def make_llm(system_prompt: str):
    s = get_settings()
    from pipecat.services.anthropic.llm import AnthropicLLMService

    return AnthropicLLMService(
        api_key=s.anthropic_api_key or "",
        settings=AnthropicLLMService.Settings(
            model=s.claude_model,
            system_instruction=system_prompt,
            effort=s.claude_live_effort,
            enable_prompt_caching=True,
            max_tokens=600,
        ),
    )


def make_serializer(transport_type: str, call_data):
    s = get_settings()
    if transport_type == "twilio":
        from pipecat.serializers.twilio import TwilioFrameSerializer

        return TwilioFrameSerializer(
            stream_sid=call_data["stream_id"],
            call_sid=call_data["call_id"],
            account_sid=s.twilio_account_sid,
            auth_token=s.twilio_auth_token,
            params=TwilioFrameSerializer.InputParams(auto_hang_up=bool(s.twilio_account_sid and s.twilio_auth_token)),
        )
    if transport_type == "plivo":
        from pipecat.serializers.plivo import PlivoFrameSerializer

        return PlivoFrameSerializer(
            stream_id=call_data["stream_id"],
            call_id=call_data["call_id"],
            auth_id=s.plivo_auth_id,
            auth_token=s.plivo_auth_token,
            params=PlivoFrameSerializer.InputParams(auto_hang_up=bool(s.plivo_auth_id and s.plivo_auth_token)),
        )
    if transport_type == "exotel":
        from pipecat.serializers.exotel import ExotelFrameSerializer

        return ExotelFrameSerializer(stream_sid=call_data["stream_id"], call_sid=call_data["call_id"])
    raise VoiceStackUnavailable(f"Unsupported telephony stream: {transport_type}")
