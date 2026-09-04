"""Pull real failed payments out of a merchant's own Razorpay account.

Read-only, on purpose: this calls `payment.all()` and nothing else -- it
never creates, updates, or charges anything, so it is safe to point at a
live account at any time. The Razorpay payment entity already carries
`error_code` / `error_description` / `error_source` / `error_step` /
`error_reason` on a failed payment, so it maps onto the same `Transaction`
/ `ErrorDetail` shapes the synthetic generator produces -- nothing
downstream (diagnosis, recovery, execution, learning) can tell the
difference between a real failure and a synthetic one.

`attempt_number` isn't part of the payment entity; it's recovered by
grouping the fetched payments by `order_id` and counting prior attempts
on the same order, chronologically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from recover_ai.domain.enums import ErrorSource, PaymentMethod, TransactionStatus
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money

_METHOD_MAP: dict[str, PaymentMethod] = {
    "card": PaymentMethod.CARD,
    "upi": PaymentMethod.UPI,
    "netbanking": PaymentMethod.NETBANKING,
    "wallet": PaymentMethod.WALLET,
    # Razorpay methods with no direct equivalent in our (buildathon-scoped)
    # PaymentMethod enum -- mapped to the closest rail rather than dropped.
    "emi": PaymentMethod.CARD,
    "paylater": PaymentMethod.WALLET,
}

_SOURCE_MAP: dict[str, ErrorSource] = {
    "business": ErrorSource.BUSINESS,
    "customer": ErrorSource.CUSTOMER,
    "bank": ErrorSource.BANK,
    "gateway": ErrorSource.GATEWAY,
    "network": ErrorSource.NETWORK,
}


def _method(raw: str | None) -> PaymentMethod:
    return _METHOD_MAP.get((raw or "").lower(), PaymentMethod.CARD)


def _source(raw: str | None) -> ErrorSource:
    return _SOURCE_MAP.get((raw or "").lower(), ErrorSource.GATEWAY)


def _to_transaction(raw: dict[str, Any], attempt_number: int) -> Transaction:
    error = ErrorDetail(
        code=str(raw.get("error_code") or "UNKNOWN"),
        description=str(raw.get("error_description") or "No description provided by Razorpay."),
        source=_source(raw.get("error_source")),
        step=str(raw.get("error_step") or "unknown"),
        reason=ErrorDetail.coerce_reason(str(raw.get("error_reason") or "")),
    )
    customer_id = str(
        raw.get("customer_id") or raw.get("contact") or raw.get("email") or f"cust_{raw['id']}"
    )
    order_id = str(raw.get("order_id") or f"order_{raw['id']}")
    return Transaction(
        id=str(raw["id"]),
        order_id=order_id,
        customer_id=customer_id,
        amount=Money.from_paise(int(raw["amount"])),
        method=_method(raw.get("method")),
        status=TransactionStatus.FAILED,
        created_at=datetime.fromtimestamp(int(raw["created_at"]), tz=UTC),
        attempt_number=attempt_number,
        error=error,
    )


def parse_failures(items: list[dict[str, Any]]) -> list[Transaction]:
    """Pure mapping step, kept separate from the network call so it's
    testable with fixture payloads -- no client, no monkeypatching."""
    failed = [p for p in items if p.get("status") == "failed"]
    failed.sort(key=lambda p: p.get("created_at", 0))

    attempts: dict[str, int] = {}
    out: list[Transaction] = []
    for raw in failed:
        order_id = str(raw.get("order_id") or raw["id"])
        attempts[order_id] = attempts.get(order_id, 0) + 1
        out.append(_to_transaction(raw, attempts[order_id]))
    return out


def fetch_recent_failures(key_id: str, key_secret: str, *, count: int = 100) -> list[Transaction]:
    """The merchant's most recent failed payments. Read-only -- no side
    effects on the Razorpay account."""
    import razorpay

    client = razorpay.Client(auth=(key_id, key_secret))
    resp: dict[str, Any] = client.payment.all({"count": min(max(count, 1), 100)})
    items: list[dict[str, Any]] = resp.get("items", [])
    return parse_failures(items)
