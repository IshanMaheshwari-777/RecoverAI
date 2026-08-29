"""Ports: the interfaces the application layer depends on.

Concrete implementations live in `recover_ai.adapters`. Services
receive a port via their constructor and never import an adapter or a
vendor SDK directly -- that's what makes them unit-testable without a
network and swappable without a rewrite.
"""

from recover_ai.ports.llm import LLMPort, LLMReply
from recover_ai.ports.payments import PaymentGatewayPort, PaymentLink

__all__ = ["LLMPort", "LLMReply", "PaymentGatewayPort", "PaymentLink"]
