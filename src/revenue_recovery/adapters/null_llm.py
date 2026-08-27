"""An LLMPort that is never available.

Used when there is no Anthropic credential. Every `complete()` raises
`LLMUnavailableError`, so callers take their deterministic fallback path
without special-casing "is the LLM configured".
"""

from __future__ import annotations

from revenue_recovery.domain.errors import LLMUnavailableError
from revenue_recovery.ports.llm import LLMReply


class NullLLM:
    @property
    def available(self) -> bool:
        return False

    @property
    def model(self) -> str:
        return "none"

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMReply:
        raise LLMUnavailableError("no Anthropic credential configured")
