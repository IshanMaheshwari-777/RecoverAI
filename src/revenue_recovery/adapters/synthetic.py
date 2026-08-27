"""Synthetic Razorpay-shaped transaction batches.

A weighted mix of captured payments, failed payments (with error objects
matching Razorpay's documented schema: code / description / source / step
/ reason), and abandoned checkouts. Seeded, so a batch is fully
reproducible -- the same seed gives byte-identical output, which is what
makes the demo's headline numbers checkable.

The `reason` values are representative examples, not scraped verbatim
from Razorpay's docs; cross-check against
https://razorpay.com/docs/errors/payments/list/ before wiring real flows.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from revenue_recovery.domain.enums import (
    ErrorSource,
    FailureReason,
    PaymentMethod,
    TransactionStatus,
)
from revenue_recovery.domain.models import ErrorDetail, Transaction
from revenue_recovery.domain.money import Money

_ALL_METHODS: list[PaymentMethod] = list(PaymentMethod)


@dataclass(frozen=True, slots=True)
class _Scenario:
    weight: float
    code: str
    description: str
    source: ErrorSource
    step: str
    reason: FailureReason
    methods: list[PaymentMethod]


_SCENARIOS: list[_Scenario] = [
    _Scenario(
        0.06,
        "BAD_REQUEST_ERROR",
        "Authentication failed due to an incorrect OTP",
        ErrorSource.CUSTOMER,
        "payment_authentication",
        FailureReason.INVALID_OTP,
        [PaymentMethod.CARD, PaymentMethod.UPI],
    ),
    _Scenario(
        0.07,
        "GATEWAY_ERROR",
        "Payment was declined by the issuing bank",
        ErrorSource.BANK,
        "payment_authorization",
        FailureReason.PAYMENT_DECLINED,
        [PaymentMethod.CARD, PaymentMethod.NETBANKING],
    ),
    _Scenario(
        0.06,
        "GATEWAY_ERROR",
        "Insufficient funds in the customer's account",
        ErrorSource.BANK,
        "payment_authorization",
        FailureReason.INSUFFICIENT_FUNDS,
        [PaymentMethod.CARD, PaymentMethod.UPI, PaymentMethod.NETBANKING],
    ),
    _Scenario(
        0.05,
        "SERVER_ERROR",
        "The payment gateway did not respond in time",
        ErrorSource.GATEWAY,
        "payment_authorization",
        FailureReason.GATEWAY_TIMEOUT,
        _ALL_METHODS,
    ),
    _Scenario(
        0.03,
        "BAD_REQUEST_ERROR",
        "Customer cancelled the payment on the checkout page",
        ErrorSource.CUSTOMER,
        "payment_initiation",
        FailureReason.PAYMENT_CANCELLED,
        _ALL_METHODS,
    ),
    _Scenario(
        0.04,
        "BAD_REQUEST_ERROR",
        "The card used for payment has expired",
        ErrorSource.CUSTOMER,
        "card_validation",
        FailureReason.CARD_EXPIRED,
        [PaymentMethod.CARD],
    ),
    _Scenario(
        0.04,
        "SERVER_ERROR",
        "Network connectivity issue during payment processing",
        ErrorSource.NETWORK,
        "payment_authorization",
        FailureReason.NETWORK_ISSUE,
        _ALL_METHODS,
    ),
    _Scenario(
        0.02,
        "BAD_REQUEST_ERROR",
        "Transaction blocked by fraud risk checks",
        ErrorSource.BUSINESS,
        "risk_check",
        FailureReason.RISK_CHECK_FAILED,
        _ALL_METHODS,
    ),
]

_CAPTURED_WEIGHT = 0.55
_ABANDONED_WEIGHT = 0.08

_AMOUNT_BANDS = [(199, 999, 0.35), (1000, 4999, 0.35), (5000, 12000, 0.22), (12000, 30000, 0.08)]


def _pick_amount(rng: random.Random) -> Money:
    r = rng.random()
    cum = 0.0
    for lo, hi, w in _AMOUNT_BANDS:
        cum += w
        if r <= cum:
            return Money(round(rng.uniform(lo, hi), 2))
    return Money(round(rng.uniform(*_AMOUNT_BANDS[-1][:2]), 2))


def _sid(prefix: str, rng: random.Random) -> str:
    return f"{prefix}_{uuid.UUID(int=rng.getrandbits(128)).hex[:14]}"


def generate_batch(
    count: int, seed: int, *, reference_time: datetime | None = None
) -> list[Transaction]:
    """Deterministic given ``seed`` and ``reference_time``. The app leaves
    ``reference_time`` unset so the batch looks recent; tests pin it for
    byte-for-byte reproducibility.
    """
    rng = random.Random(seed)
    customer_pool = [_sid("cust", rng) for _ in range(max(20, count // 3))]

    keys = ["captured", *[str(i) for i in range(len(_SCENARIOS))], "abandoned"]
    weights = [_CAPTURED_WEIGHT, *[s.weight for s in _SCENARIOS], _ABANDONED_WEIGHT]

    now = reference_time or datetime.now(tz=UTC)
    out: list[Transaction] = []

    for _ in range(count):
        outcome = rng.choices(keys, weights=weights, k=1)[0]
        created = now - timedelta(days=rng.uniform(0, 14), hours=rng.uniform(0, 24))
        customer = rng.choice(customer_pool)
        order_id = _sid("order", rng)
        pay_id = _sid("pay", rng)
        amount = _pick_amount(rng)

        if outcome == "captured":
            out.append(
                Transaction(
                    id=pay_id,
                    order_id=order_id,
                    customer_id=customer,
                    amount=amount,
                    method=rng.choice(_ALL_METHODS),
                    status=TransactionStatus.CAPTURED,
                    created_at=created,
                )
            )
        elif outcome == "abandoned":
            out.append(
                Transaction(
                    id=order_id.replace("order", "pay"),
                    order_id=order_id,
                    customer_id=customer,
                    amount=amount,
                    method=rng.choice(_ALL_METHODS),
                    status=TransactionStatus.ABANDONED,
                    created_at=created,
                )
            )
        else:
            s = _SCENARIOS[int(outcome)]
            out.append(
                Transaction(
                    id=pay_id,
                    order_id=order_id,
                    customer_id=customer,
                    amount=amount,
                    method=rng.choice(s.methods),
                    status=TransactionStatus.FAILED,
                    created_at=created,
                    attempt_number=rng.choice([1, 1, 1, 2, 2, 3]),
                    error=ErrorDetail(
                        code=s.code,
                        description=s.description,
                        source=s.source,
                        step=s.step,
                        reason=s.reason,
                    ),
                )
            )

    out.sort(key=lambda t: t.created_at)
    return out
