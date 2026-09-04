"""`source="razorpay"` wiring in `run_pipeline` -- no real network in tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from recover_ai import app as app_module
from recover_ai.app import run_pipeline
from recover_ai.domain.enums import ErrorSource, FailureReason, PaymentMethod, TransactionStatus
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money


def test_razorpay_source_without_credentials_raises() -> None:
    with pytest.raises(ValueError, match="RAZORPAY_KEY_ID"):
        run_pipeline(source="razorpay")


def test_razorpay_source_uses_the_ingestion_adapter_not_synthetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "fake_secret")
    from recover_ai.config import get_settings

    get_settings.cache_clear()

    fake_txn = Transaction(
        id="pay_live_1",
        order_id="order_live_1",
        customer_id="cust_live_1",
        amount=Money(2500),
        method=PaymentMethod.UPI,
        status=TransactionStatus.FAILED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        error=ErrorDetail(
            code="X",
            description="x",
            source=ErrorSource.BANK,
            step="payment_authorization",
            reason=FailureReason.PAYMENT_DECLINED,
        ),
    )
    called: dict[str, object] = {}

    def _fake_fetch(key_id: str, key_secret: str, *, count: int = 100) -> list[Transaction]:
        called["key_id"] = key_id
        called["count"] = count
        return [fake_txn]

    monkeypatch.setattr(app_module, "fetch_recent_failures", _fake_fetch)

    report = run_pipeline(source="razorpay", count=25)

    assert called["key_id"] == "rzp_test_fake"
    assert called["count"] == 25
    assert report.data_source == "razorpay"
    assert report.summary.total_transactions == 1
    assert report.results[0].transaction_id == "pay_live_1"
    get_settings.cache_clear()


def test_real_data_is_idempotent_across_runs() -> None:
    """Unlike synthetic data, a real transaction id must never be executed
    twice -- running the same fetched batch again should not re-create a
    second payment link / message for it. Exercises the Pipeline directly
    (SimulatedGateway/NullLLM) so this stays a unit test, not a network call."""
    from recover_ai.adapters.null_llm import NullLLM
    from recover_ai.adapters.simulated_gateway import SimulatedGateway
    from recover_ai.config import get_settings
    from recover_ai.domain.policy import Policy
    from recover_ai.services.idempotency import IdempotencyStore
    from recover_ai.services.pipeline import Pipeline

    fake_txn = Transaction(
        id="pay_live_dup",
        order_id="order_live_dup",
        customer_id="cust_live_dup",
        amount=Money(2500),
        method=PaymentMethod.UPI,
        status=TransactionStatus.FAILED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        error=ErrorDetail(
            code="X",
            description="x",
            source=ErrorSource.BANK,
            step="payment_authorization",
            reason=FailureReason.PAYMENT_DECLINED,
        ),
    )
    idem = IdempotencyStore()
    pipe = Pipeline(
        settings=get_settings(),
        llm=NullLLM(),
        gateway=SimulatedGateway(),
        policy=Policy(holdout_fraction=0.0),  # a 1-txn batch would otherwise always hold out
        idempotency=idem,
    )

    first = pipe.run([fake_txn], seed=1, count=1, data_source="razorpay")
    second = pipe.run([fake_txn], seed=1, count=1, data_source="razorpay")

    first_entry = first.results[0].audit_entry
    second_entry = second.results[0].audit_entry
    assert first_entry.executed is True
    assert second_entry.executed is False
    assert "idempotency" in second_entry.detail


def test_razorpay_source_with_zero_real_failures_is_a_clean_empty_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "fake_secret")
    from recover_ai.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(app_module, "fetch_recent_failures", lambda *a, **k: [])

    report = run_pipeline(source="razorpay")
    assert report.data_source == "razorpay"
    assert report.summary.total_transactions == 0
    assert report.summary.needing_attention == 0
    assert report.results == []
    get_settings.cache_clear()
