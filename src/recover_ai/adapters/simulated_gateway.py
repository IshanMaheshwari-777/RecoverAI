"""A PaymentGatewayPort that never touches the network."""

from __future__ import annotations

import uuid

from recover_ai.domain.enums import ExecutionMethod
from recover_ai.domain.money import Money
from recover_ai.ports.payments import PaymentLink


class SimulatedGateway:
    """Produces plausibly-shaped payment links, clearly labelled as fake."""

    live = False

    def create_payment_link(
        self, *, amount: Money, order_id: str, description: str, note: str
    ) -> PaymentLink:
        token = uuid.uuid4().hex
        return PaymentLink(
            id=f"plink_SIM{token[:14]}",
            short_url=f"https://rzp.io/i/{token[:8]}",
            amount=amount,
            method=ExecutionMethod.RAZORPAY_API_SIMULATED,
        )
