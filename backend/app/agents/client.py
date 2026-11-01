"""The only module that talks to the model provider."""

from typing import Any, Protocol

import anthropic

from app.core.config import get_settings

MAX_TOKENS = 4096
TIMEOUT_SECONDS = 60
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """The provider failed. Holds no request content, so it's safe to log."""


class LLMClient(Protocol):
    def create(self, system: str, tools: list[dict], messages: list[dict]) -> Any:
        """Returns a message with `stop_reason` and `content` blocks."""


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)
        self._model = model

    def create(self, system: str, tools: list[dict], messages: list[dict]) -> Any:
        try:
            return self._client.beta.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": "low"},
                cache_control={"type": "ephemeral"},
                # A false safety decline retries on another model rather than failing the chat.
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIError as error:
            raise LLMError(type(error).__name__) from error


def get_llm() -> LLMClient | None:
    """None means no key is configured: chat is off and hand ordering still works."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return AnthropicClient(settings.anthropic_api_key, settings.ai_model)
