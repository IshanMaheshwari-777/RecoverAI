"""Replay a policy over a historical outcome log.

Given a CSV of past failed payments *with the outcome that actually
happened*, run diagnosis + recovery + the economics gate over each row
and compare what the policy would have done and projected against what
really occurred. The output is the artefact a merchant wants before
switching anything on: "on your last N failures, this policy recovers an
estimated ₹X, +Y% over what happened."

CSV columns (header row required):
    transaction_id, customer_id, amount, method, status, reason,
    attempt_number, created_at, actual_recovered

`actual_recovered` is 1/0/true/false -- whether that payment was
ultimately completed. `status` is failed|abandoned; `reason` may be blank
for abandoned rows.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from recover_ai.domain.enums import (
    ErrorSource,
    FailureReason,
    PaymentMethod,
    TransactionStatus,
)
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money
from recover_ai.domain.policy import Policy
from recover_ai.ports.llm import LLMPort
from recover_ai.services.diagnosis import DiagnosisEngine
from recover_ai.services.economics import best_channel
from recover_ai.services.learning import LearningStore, conversion_key
from recover_ai.services.recovery import RecoveryEngine

_TRUTHY = {"1", "true", "yes", "y", "recovered"}


@dataclass(slots=True)
class BacktestResult:
    rows: int = 0
    would_act: int = 0
    skipped_negative_ev: int = 0
    blocked: int = 0
    actual_recovered_revenue: Money = field(default_factory=Money.zero)
    projected_recovered_revenue: Money = field(default_factory=Money.zero)
    organic_recovered_revenue: Money = field(default_factory=Money.zero)
    brier_score: float = 0.0

    @property
    def incremental_revenue(self) -> Money:
        return self.projected_recovered_revenue - self.organic_recovered_revenue

    def as_dict(self) -> dict[str, object]:
        return {
            "rows": self.rows,
            "would_act": self.would_act,
            "skipped_negative_ev": self.skipped_negative_ev,
            "blocked": self.blocked,
            "actual_recovered": float(self.actual_recovered_revenue.rupees),
            "projected_recovered": float(self.projected_recovered_revenue.rupees),
            "organic_baseline": float(self.organic_recovered_revenue.rupees),
            "incremental_revenue": float(self.incremental_revenue.rupees),
            "brier_score": round(self.brier_score, 4),
        }


def _row_to_txn(row: dict[str, str]) -> Transaction:
    reason_raw = (row.get("reason") or "").strip()
    status = TransactionStatus(row["status"].strip())
    error = None
    if status is TransactionStatus.FAILED and reason_raw:
        error = ErrorDetail(
            code="BACKTEST",
            description=reason_raw,
            source=ErrorSource.BANK,
            step="payment_authorization",
            reason=FailureReason(reason_raw),
        )
    created = row.get("created_at") or ""
    return Transaction(
        id=row["transaction_id"].strip(),
        order_id=f"order_{row['transaction_id'].strip()}",
        customer_id=row["customer_id"].strip(),
        amount=Money(row["amount"].strip()),
        method=PaymentMethod(row["method"].strip()),
        status=status,
        created_at=datetime.fromisoformat(created) if created else datetime.now(tz=UTC),
        attempt_number=int(row.get("attempt_number") or 1),
        error=error,
    )


def run_backtest(csv_path: str | Path, policy: Policy, llm: LLMPort) -> BacktestResult:
    diagnoser = DiagnosisEngine(llm)
    engine = RecoveryEngine(policy)
    learning = LearningStore(policy)
    result = BacktestResult()
    brier_sum = 0.0
    brier_n = 0

    with Path(csv_path).open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: r.get("created_at") or "")

    for row in rows:
        txn = _row_to_txn(row)
        actual = (row.get("actual_recovered") or "").strip().lower() in _TRUTHY
        result.rows += 1

        diag = diagnoser.diagnose(txn)
        decision = engine.decide(txn, diag)
        if decision.blocked or decision.final_action is None:
            result.blocked += 1
            if actual:
                result.actual_recovered_revenue += txn.amount
            continue

        action = decision.final_action
        band = policy.amount_band(float(txn.amount.rupees))
        key = conversion_key(action, txn.method, txn.reason, band)
        rate = learning.rate(key)
        ev = best_channel(
            policy=policy,
            action=action,
            amount=float(txn.amount.rupees),
            p_recover=rate,
            deliverable=lambda _c: True,
        )

        if actual:
            result.actual_recovered_revenue += txn.amount

        if not ev.worth_pursuing:
            result.skipped_negative_ev += 1
            continue

        result.would_act += 1
        learning.observe_conversion(key, converted=actual, predicted=rate)
        brier_sum += (rate - (1.0 if actual else 0.0)) ** 2
        brier_n += 1
        result.projected_recovered_revenue += txn.amount * rate
        result.organic_recovered_revenue += txn.amount * policy.organic_recovery_rate

    result.brier_score = brier_sum / brier_n if brier_n else 0.0
    return result
