"""LLMPort backed by the Anthropic Messages API."""

from __future__ import annotations

import time
from typing import Any

from revenue_recovery.domain.errors import LLMUnavailableError
from revenue_recovery.logging import get_logger
from revenue_recovery.ports.llm import LLMReply

log = get_logger(__name__)

# `output_config.effort` is only accepted on the Opus-5 / Sonnet-5 / Fable
# tiers; Haiku 4.5 (the default) and older models 400 on it.
_EFFORT_MODELS = ("claude-opus-5", "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-5",
                  "claude-fable-5")


class AnthropicLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None  # lazily constructed anthropic.Anthropic

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise LLMUnavailableError("anthropic SDK not installed") from exc
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, prompt: str, *, max_tokens: int = 512) -> LLMReply:
        client = self._ensure_client()
        extra: dict[str, Any] = {}
        if self._model.startswith(_EFFORT_MODELS):
            extra["output_config"] = {"effort": "low"}

        started = time.perf_counter()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                **extra,
            )
        except Exception as exc:
            log.warning("llm_call_failed", error=str(exc))
            raise LLMUnavailableError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            raise LLMUnavailableError("LLM returned no text content")
        return LLMReply(text=text, model=self._model, latency_ms=latency_ms)
