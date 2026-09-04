"""Mapping real Razorpay payment payloads onto the domain model.

Pure function, no network -- `parse_failures` takes exactly the shape
`client.payment.all()` returns.
"""

from __future__ import annotations

from recover_ai.adapters.razorpay_ingest import parse_failures
from recover_ai.domain.enums import (
    ErrorSource,
    FailureReason,
    PaymentMethod,
    TransactionStatus,
)


def _payment(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "pay_abc123",
        "order_id": "order_xyz789",
        "amount": 150000,
        "method": "card",
        "status": "failed",
        "created_at": 1_735_689_600,  # 2025-01-01T00:00:00Z
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment failed",
        "error_source": "bank",
        "error_step": "payment_authorization",
        "error_reason": "payment_declined",
        "contact": "+919999999999",
    }
    base.update(overrides)
    return base


def test_only_failed_payments_survive() -> None:
    out = parse_failures([_payment(status="captured"), _payment(id="pay_2")])
    assert len(out) == 1
    assert out[0].id == "pay_2"


def test_maps_amount_method_and_error_shape() -> None:
    [txn] = parse_failures([_payment()])
    assert txn.status is TransactionStatus.FAILED
    assert txn.method is PaymentMethod.CARD
    assert float(txn.amount.rupees) == 1500.0  # 150000 paise
    assert txn.error is not None
    assert txn.error.reason is FailureReason.PAYMENT_DECLINED
    assert txn.error.source is ErrorSource.BANK


def test_unrecognised_reason_falls_back_to_unknown() -> None:
    [txn] = parse_failures([_payment(error_reason="some_new_razorpay_code")])
    assert txn.error is not None
    assert txn.error.reason is FailureReason.UNKNOWN


def test_unmapped_method_falls_back_to_card() -> None:
    [txn] = parse_failures([_payment(method="emi")])
    assert txn.method is PaymentMethod.CARD


def test_attempt_number_counts_prior_failures_on_the_same_order() -> None:
    items = [
        _payment(id="pay_1", order_id="order_shared", created_at=100),
        _payment(id="pay_2", order_id="order_shared", created_at=200),
        _payment(id="pay_3", order_id="order_other", created_at=150),
    ]
    out = {t.id: t for t in parse_failures(items)}
    assert out["pay_1"].attempt_number == 1
    assert out["pay_2"].attempt_number == 2  # 2nd failure on the same order
    assert out["pay_3"].attempt_number == 1  # different order, its own count


def test_missing_customer_id_falls_back_to_contact_then_a_derived_id() -> None:
    [txn] = parse_failures([_payment(contact=None, email=None)])
    assert txn.customer_id == "cust_pay_abc123"


def test_no_failures_returns_empty_list() -> None:
    assert parse_failures([]) == []
    assert parse_failures([_payment(status="captured")]) == []
