from datetime import UTC, datetime

from revenue_recovery.adapters.synthetic import generate_batch
from revenue_recovery.domain.enums import TransactionStatus
from revenue_recovery.domain.money import Money

_FIXED = datetime(2026, 6, 1, tzinfo=UTC)


def test_generates_requested_count() -> None:
    assert len(generate_batch(200, seed=1)) == 200


def test_same_seed_is_byte_identical() -> None:
    a = generate_batch(100, seed=7, reference_time=_FIXED)
    b = generate_batch(100, seed=7, reference_time=_FIXED)
    assert [t.model_dump_json() for t in a] == [t.model_dump_json() for t in b]


def test_failed_transactions_carry_an_error_object() -> None:
    failed = [t for t in generate_batch(300, seed=5) if t.status is TransactionStatus.FAILED]
    assert failed
    assert all(t.error is not None for t in failed)


def test_captured_and_abandoned_have_no_error() -> None:
    for t in generate_batch(300, seed=5):
        if t.status in (TransactionStatus.CAPTURED, TransactionStatus.ABANDONED):
            assert t.error is None


def test_amounts_are_positive_money() -> None:
    assert all(t.amount > Money.zero() for t in generate_batch(150, seed=3))


def test_capture_ratio_is_in_a_sane_band() -> None:
    txns = generate_batch(2000, seed=11)
    captured = sum(1 for t in txns if t.status is TransactionStatus.CAPTURED)
    assert 0.45 < captured / len(txns) < 0.65
