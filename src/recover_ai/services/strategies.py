"""Per-method recovery playbooks and the retry-scheduling model.

Two payment methods failing the same way don't want the same treatment.
A UPI timeout is worth retrying in minutes (rails are instant, cost is
zero); a net-banking failure often means the bank is down and is worth
waiting hours on; a second card decline is a signal to move the customer
to a different rail entirely. These differences are small but they're
exactly the kind of judgement a merchant's own ops team applies by hand,
and encoding them is what makes the agent more than a retry loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from recover_ai.domain.enums import FailureReason, PaymentMethod


@dataclass(frozen=True, slots=True)
class RecoveryStrategy:
    name: str
    max_retries: int  # attempts on the same method before escalating
    base_retry_delay: timedelta  # for a retry_later on this method
    alternate_method: PaymentMethod  # what to suggest when we escalate

    def escalation_hint(self) -> str:
        return f"suggest paying by {self.alternate_method.value} instead"


_STRATEGIES: dict[PaymentMethod, RecoveryStrategy] = {
    PaymentMethod.CARD: RecoveryStrategy(
        name="card",
        max_retries=3,
        base_retry_delay=timedelta(hours=6),
        alternate_method=PaymentMethod.UPI,
    ),
    PaymentMethod.UPI: RecoveryStrategy(
        name="upi",
        max_retries=3,
        base_retry_delay=timedelta(minutes=20),  # instant rails, cheap to retry
        alternate_method=PaymentMethod.NETBANKING,
    ),
    PaymentMethod.NETBANKING: RecoveryStrategy(
        name="netbanking",
        max_retries=2,
        base_retry_delay=timedelta(hours=12),  # usually a bank-side outage
        alternate_method=PaymentMethod.UPI,
    ),
    PaymentMethod.WALLET: RecoveryStrategy(
        name="wallet",
        max_retries=2,
        base_retry_delay=timedelta(hours=3),
        alternate_method=PaymentMethod.CARD,
    ),
}

# How long to wait before a delayed retry, by root cause. The method's
# base delay is a floor; a cause that needs real-world time to resolve
# (funds arriving) overrides it.
_CAUSE_DELAY: dict[FailureReason, timedelta] = {
    FailureReason.INSUFFICIENT_FUNDS: timedelta(hours=24),
    FailureReason.GATEWAY_TIMEOUT: timedelta(minutes=15),
    FailureReason.NETWORK_ISSUE: timedelta(minutes=15),
    FailureReason.PAYMENT_DECLINED: timedelta(hours=6),
}


def strategy_for(method: PaymentMethod) -> RecoveryStrategy:
    return _STRATEGIES[method]


def retry_delay(
    method: PaymentMethod, reason: FailureReason | None, attempt_number: int
) -> timedelta:
    """Delay before a `retry_later` should fire. Grows with prior attempts."""
    strat = strategy_for(method)
    cause_floor = _CAUSE_DELAY.get(reason, timedelta(0)) if reason else timedelta(0)
    base = max(strat.base_retry_delay, cause_floor)
    # exponential-ish backoff on repeated attempts, capped at 48h
    scaled: timedelta = base * (2 ** max(0, attempt_number - 1))
    return min(scaled, timedelta(hours=48))
