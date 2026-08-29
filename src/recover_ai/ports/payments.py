from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from recover_ai.domain.enums import ExecutionMethod
from recover_ai.domain.money import Money


@dataclass(frozen=True, slots=True)
class PaymentLink:
    id: str
    short_url: str
    amount: Money
    method: ExecutionMethod  # how it was actually produced (live / simulated / rate-limited)


class PaymentGatewayPort(Protocol):
    """Creates a fresh place for a customer to pay.

    You cannot silently re-charge a card that already declined -- the real
    recovery mechanism is handing the customer a new payment link. The
    live implementation talks to Razorpay; a simulated one lets the whole
    pipeline run before any account setup.
    """

    @property
    def live(self) -> bool: ...

    def create_payment_link(
        self, *, amount: Money, order_id: str, description: str, note: str
    ) -> PaymentLink: ...
