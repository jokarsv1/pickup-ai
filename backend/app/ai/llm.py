"""Thin wrapper over the Anthropic SDK used outside the live call (summaries, intent, chat).

The live call itself runs through Pipecat's AnthropicLLMService (see app/voice/pipeline.py).

Server-side refusal fallbacks are on for models that have them (Opus, Sonnet, Fable): if the main
model declines a request, the API retries it on a fallback model inside the same call. Claude
Haiku 5.5 has no server-side fallback, so its requests go without (a refusal raises LLMError).
"""

from typing import Any, Protocol, TypeVar

import anthropic
from loguru import logger
from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def fallback_args(model: str) -> dict[str, Any]:
    """Request fields that turn on server-side refusal fallbacks, for models that support them."""
    if "haiku" in model:
        return {}
    return {"betas": [FALLBACK_BETA], "fallbacks": "default"}


class LLMError(Exception):
    pass


class LLM(Protocol):
    async def structured(self, *, system: str, prompt: str, schema: type[T], effort: str = "low", max_tokens: int = 4000) -> T: ...

    async def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], effort: str = "medium", max_tokens: int = 8000
    ) -> Any: ...


class ClaudeLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=3)
        self._model = model

    async def structured(self, *, system: str, prompt: str, schema: type[T], effort: str = "low", max_tokens: int = 4000) -> T:
        try:
            response = await self._client.beta.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                output_config={"effort": effort},
                **fallback_args(self._model),
            )
        except anthropic.APIError as exc:
            raise LLMError(str(exc)) from exc
        if response.stop_reason == "refusal":
            raise LLMError("The model declined this request")
        if response.parsed_output is None:
            raise LLMError(f"No structured output (stop_reason={response.stop_reason})")
        return response.parsed_output

    async def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], effort: str = "medium", max_tokens: int = 8000
    ) -> Any:
        try:
            return await self._client.beta.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=tools,
                output_config={"effort": effort},
                **fallback_args(self._model),
            )
        except anthropic.APIError as exc:
            raise LLMError(str(exc)) from exc


class DisabledLLM:
    async def structured(self, **_: Any) -> Any:
        raise LLMError("AI is not configured (set ANTHROPIC_API_KEY)")

    async def create(self, **_: Any) -> Any:
        raise LLMError("AI is not configured (set ANTHROPIC_API_KEY)")


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        s = get_settings()
        if s.anthropic_api_key:
            _llm = ClaudeLLM(s.anthropic_api_key, s.claude_model)
        else:
            logger.info("ANTHROPIC_API_KEY not set: AI features are off")
            _llm = DisabledLLM()
    return _llm


def set_llm(llm: LLM | None) -> None:
    global _llm
    _llm = llm


def content_to_dicts(content: Any) -> list[dict[str, Any]]:
    """Serialize response content blocks so they can be replayed verbatim on the next turn."""
    blocks: list[dict[str, Any]] = []
    for block in content or []:
        if isinstance(block, dict):
            blocks.append(block)
        else:
            blocks.append(block.model_dump(mode="json", exclude_none=True))
    return blocks
