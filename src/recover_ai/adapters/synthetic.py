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

from recover_ai.domain.enums import (
    DiagnosisAction,
    ErrorSource,
    FailureReason,
    PaymentMethod,
    TransactionStatus,
)
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money
from recover_ai.domain.policy import Policy

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


# -- historical outcomes for the learning warm-start --------------------

# "True" conversion rates the learning loop should discover -- deliberately
# a little different from the policy priors, so the calibration curve shows
# the model moving off its prior toward reality.
_TRUE_RATE: dict[DiagnosisAction, float] = {
    DiagnosisAction.RETRY_NOW: 0.52,
    DiagnosisAction.RETRY_LATER: 0.34,
    DiagnosisAction.SEND_REMINDER: 0.17,
    DiagnosisAction.REQUEST_UPDATE: 0.19,
}
_REASON_BY_ACTION: dict[DiagnosisAction, list[FailureReason]] = {
    DiagnosisAction.RETRY_NOW: [
        FailureReason.INVALID_OTP,
        FailureReason.GATEWAY_TIMEOUT,
        FailureReason.NETWORK_ISSUE,
    ],
    DiagnosisAction.RETRY_LATER: [FailureReason.INSUFFICIENT_FUNDS, FailureReason.PAYMENT_DECLINED],
    DiagnosisAction.SEND_REMINDER: [FailureReason.PAYMENT_CANCELLED],
    DiagnosisAction.REQUEST_UPDATE: [FailureReason.CARD_EXPIRED, FailureReason.PAYMENT_DECLINED],
}


def generate_history(
    policy: Policy, seed: int, *, observations: int = 320
) -> list[tuple[str, bool, float]]:
    """Deterministic (conversion_key, converted, predicted_at_the_time)
    tuples -- a plausible outcome log to warm-start the learning loop so a
    fresh install still has calibrated posteriors and a reliability curve.
    """
    from recover_ai.services.learning import conversion_key

    rng = random.Random(f"history-{seed}")
    actions = [
        DiagnosisAction.RETRY_NOW,
        DiagnosisAction.RETRY_LATER,
        DiagnosisAction.SEND_REMINDER,
        DiagnosisAction.REQUEST_UPDATE,
    ]
    bands = [policy.amount_band(x) for x in (500, 2500, 8000, 20000)]
    rows: list[tuple[str, bool, float]] = []
    for _ in range(observations):
        action = rng.choice(actions)
        method = rng.choice(_ALL_METHODS)
        reason = rng.choice(_REASON_BY_ACTION[action])
        band = rng.choice(bands)
        true_rate = _TRUE_RATE[action] * rng.uniform(0.85, 1.15)
        converted = rng.random() < min(true_rate, 0.95)
        predicted = policy.conversion_priors.mean_for(action)
        rows.append((conversion_key(action, method, reason, band), converted, predicted))
    return rows
