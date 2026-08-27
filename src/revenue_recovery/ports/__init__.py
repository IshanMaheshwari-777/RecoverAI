"""Ports: the interfaces the application layer depends on.

Concrete implementations live in `revenue_recovery.adapters`. Services
receive a port via their constructor and never import an adapter or a
vendor SDK directly -- that's what makes them unit-testable without a
network and swappable without a rewrite.
"""

from revenue_recovery.ports.llm import LLMPort, LLMReply
from revenue_recovery.ports.payments import PaymentGatewayPort, PaymentLink

__all__ = ["LLMPort", "LLMReply", "PaymentGatewayPort", "PaymentLink"]
