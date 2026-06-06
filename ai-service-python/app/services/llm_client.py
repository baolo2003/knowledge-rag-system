"""
LLM Client Service

OpenAI-compatible client configured for DeepSeek (default).
Supports both streaming and non-streaming chat completions.

Knowledge Q&A defaults: temperature=0.3 (low for factual accuracy).
"""

from __future__ import annotations

import logging
from typing import Any, Generator, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    OpenAI-compatible LLM client.

    Usage::

        client = LLMClient.get_instance()

        # Non-streaming
        answer, usage = client.chat(messages)

        # Streaming
        for chunk in client.chat_stream(messages):
            print(chunk, end="")
    """

    _instance: Optional["LLMClient"] = None

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None
        self._model: str = settings.LLM_MODEL_NAME
        self._max_tokens: int = settings.LLM_MAX_TOKENS

    # ---- Singleton ----

    @classmethod
    def get_instance(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- Public API ----

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> tuple[str, dict[str, int]]:
        """
        Non-streaming chat completion.

        Args:
            messages:    List of {"role": ..., "content": ...} dicts.
            temperature: LLM temperature (default 0.3 for factual QA).
            max_tokens:  Max tokens to generate (default from config).
            stream:      If True, returns a generator. Use chat_stream() instead.

        Returns:
            Tuple of (answer_text, token_usage_dict).
            token_usage: {"prompt_tokens", "completion_tokens", "total_tokens"}.
        """
        client = self._get_client()
        mt = max_tokens or self._max_tokens

        logger.info(
            "LLM chat: model=%s, msgs=%d, temp=%.2f, max_tokens=%d",
            self._model, len(messages), temperature, mt,
        )

        response: ChatCompletion = client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=mt,
            stream=False,
        )

        choice = response.choices[0]
        answer = choice.message.content or ""

        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }

        logger.info(
            "LLM response: len=%d, tokens=%s",
            len(answer), usage,
        )
        return answer, usage

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> Generator[str, None, dict[str, int]]:
        """
        Streaming chat completion.

        Yields text chunks as they arrive.
        After iteration, the final token usage is available via
        ``generator.close()`` return value pattern.

        Usage::

            usage = {}
            for chunk in client.chat_stream(messages):
                yield chunk
            # After loop, usage is not directly available with generators.
            # Use the non-streaming version or wrap in a helper.

        Returns:
            Generator yielding content string fragments.
            Send a token_usage dict back via ``generator.throw()`` pattern,
            or simply use chat() for convenience.
        """
        client = self._get_client()
        mt = max_tokens or self._max_tokens

        logger.info(
            "LLM stream: model=%s, msgs=%d, temp=%.2f",
            self._model, len(messages), temperature,
        )

        stream_response = client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=mt,
            stream=True,
        )

        accumulated: list[str] = []
        usage_info: dict[str, int] = {}

        for chunk in stream_response:
            delta = chunk.choices[0].delta if chunk.choices else None
            content = delta.content if delta else None

            if content:
                accumulated.append(content)
                yield content

            # Capture usage from the last chunk
            if chunk.usage:
                usage_info = {
                    "prompt_tokens": chunk.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.usage.completion_tokens or 0,
                    "total_tokens": chunk.usage.total_tokens or 0,
                }

        logger.info(
            "LLM stream done: total_chars=%d, usage=%s",
            sum(len(c) for c in accumulated), usage_info,
        )

    # ---- Private ----

    def _get_client(self) -> OpenAI:
        """Lazy-init the OpenAI client."""
        if self._client is None:
            api_key = settings.LLM_API_KEY or "sk-placeholder"
            base_url = settings.LLM_BASE_URL

            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            logger.info(
                "LLM client initialized: provider=%s, base_url=%s, model=%s",
                settings.LLM_PROVIDER, base_url, self._model,
            )
        return self._client


# ============================================================
# Module-level convenience
# ============================================================

def get_llm_client() -> LLMClient:
    """Return the singleton LLMClient."""
    return LLMClient.get_instance()


def llm_chat(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
) -> tuple[str, dict[str, int]]:
    """Convenience: non-streaming chat."""
    return get_llm_client().chat(messages, temperature=temperature)
