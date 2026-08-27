from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMReply:
    text: str
    model: str
    latency_ms: int


class LLMPort(Protocol):
    """A minimal text-in / text-out LLM.

    The agent only ever asks the LLM to *reason and recommend* -- diagnose
    an ambiguous decline, or draft a customer message. It is never on the
    path that moves money. Implementations must raise
    `LLMUnavailableError` (not a vendor exception) when they cannot serve
    a request, so callers can fall back deterministically.
    """

    @property
    def available(self) -> bool:
        """True if a real call would be attempted (credential present)."""
        ...

    @property
    def model(self) -> str: ...

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMReply: ...
