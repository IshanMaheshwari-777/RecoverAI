from __future__ import annotations

from datetime import UTC, datetime, timedelta

from recover_ai.domain.enums import FailureReason, PaymentMethod
from recover_ai.domain.policy import Policy
from recover_ai.services.incidents import detect
from tests.conftest import make_txn


def _batch(n_incident: int, spread_minutes: int, n_other: int) -> list:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(n_incident):
        rows.append(
            make_txn(
                id=f"inc{i}",
                method=PaymentMethod.NETBANKING,
                reason=FailureReason.GATEWAY_TIMEOUT,
                created_at=(
                    base + timedelta(minutes=i * spread_minutes / max(n_incident, 1))
                ).isoformat(),
            )
        )
    for i in range(n_other):
        rows.append(
            make_txn(
                id=f"o{i}",
                method=PaymentMethod.CARD,
                reason=FailureReason.INVALID_OTP,
                created_at=(base + timedelta(hours=6 + i)).isoformat(),
            )
        )
    return rows


def test_concentrated_rail_failures_are_flagged_as_an_incident() -> None:
    incidents = detect(_batch(n_incident=12, spread_minutes=30, n_other=8), Policy())
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.method is PaymentMethod.NETBANKING
    assert inc.reason is FailureReason.GATEWAY_TIMEOUT


def test_a_few_scattered_failures_are_not_an_incident() -> None:
    # same count, but spread over 10 hours -> not concentrated
    incidents = detect(_batch(n_incident=12, spread_minutes=600, n_other=40), Policy())
    assert incidents == []


def test_below_min_events_is_never_an_incident() -> None:
    incidents = detect(_batch(n_incident=3, spread_minutes=10, n_other=2), Policy())
    assert incidents == []
