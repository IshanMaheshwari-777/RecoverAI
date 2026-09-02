from __future__ import annotations

import csv

from recover_ai.domain.policy import Policy
from recover_ai.services.backtest import run_backtest
from tests.conftest import FakeLLM

_ROWS = [
    ("pay_1", "c1", "1200", "card", "failed", "invalid_otp", "1", "2026-01-01T00:00:00+00:00", "1"),
    (
        "pay_2",
        "c2",
        "5400",
        "upi",
        "failed",
        "gateway_timeout",
        "1",
        "2026-01-01T01:00:00+00:00",
        "0",
    ),
    (
        "pay_3",
        "c3",
        "300",
        "card",
        "failed",
        "risk_check_failed",
        "1",
        "2026-01-01T02:00:00+00:00",
        "0",
    ),
    (
        "pay_4",
        "c4",
        "9000",
        "netbanking",
        "failed",
        "insufficient_funds",
        "1",
        "2026-01-01T03:00:00+00:00",
        "1",
    ),
    ("pay_5", "c5", "150", "wallet", "abandoned", "", "1", "2026-01-01T04:00:00+00:00", "0"),
]
_HEADER = [
    "transaction_id",
    "customer_id",
    "amount",
    "method",
    "status",
    "reason",
    "attempt_number",
    "created_at",
    "actual_recovered",
]


def _write_csv(path) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HEADER)
        w.writerows(_ROWS)


def test_backtest_replays_and_reports_lift(tmp_path) -> None:
    csv_path = tmp_path / "history.csv"
    _write_csv(csv_path)

    result = run_backtest(csv_path, Policy(), FakeLLM(available=False))

    assert result.rows == 5
    # risk_check_failed is blocked, not acted on
    assert result.blocked >= 1
    assert result.would_act >= 2
    # projection sits between zero and the total at-risk
    assert result.projected_recovered_revenue.rupees > 0
    assert result.incremental_revenue.rupees > 0  # beats the organic baseline
    assert 0.0 <= result.brier_score <= 1.0


def test_backtest_is_deterministic(tmp_path) -> None:
    csv_path = tmp_path / "h.csv"
    _write_csv(csv_path)
    a = run_backtest(csv_path, Policy(), FakeLLM(available=False)).as_dict()
    b = run_backtest(csv_path, Policy(), FakeLLM(available=False)).as_dict()
    assert a == b
