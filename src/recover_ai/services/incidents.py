"""Incident detection: spot an infrastructure problem, not 20 recoveries.

If a third of a batch fails on `gateway_timeout` for `netbanking` inside
forty minutes, that is one acquirer incident -- not twenty independent
customers to chase. Piling retries onto a struggling rail makes it worse.

This groups failed transactions by `(reason, method)`, and flags a group
that is both large enough (`min_events`) and concentrated enough in time
(`window_minutes`) to look like an incident rather than noise. While an
incident is active for a rail, the recovery engine defers retries against
it -- see `RecoveryEngine(retry_hold_rails=...)`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from recover_ai.domain.enums import FailureReason, PaymentMethod, TransactionStatus
from recover_ai.domain.models import Transaction
from recover_ai.domain.policy import Policy

_INFRA_REASONS = {
    FailureReason.GATEWAY_TIMEOUT,
    FailureReason.NETWORK_ISSUE,
    FailureReason.PAYMENT_DECLINED,
}


@dataclass(frozen=True, slots=True)
class Incident:
    reason: FailureReason
    method: PaymentMethod
    count: int
    share: float
    window_minutes: int

    @property
    def rail_key(self) -> tuple[FailureReason, PaymentMethod]:
        return (self.reason, self.method)

    def as_dict(self) -> dict[str, object]:
        return {
            "reason": self.reason.value,
            "method": self.method.value,
            "count": self.count,
            "share": round(self.share, 3),
            "window_minutes": self.window_minutes,
            "action_taken": f"retries against {self.method.value} deferred while degraded",
        }


def detect(transactions: list[Transaction], policy: Policy) -> list[Incident]:
    failed = [
        t
        for t in transactions
        if t.status is TransactionStatus.FAILED and t.reason in _INFRA_REASONS
    ]
    if not failed:
        return []

    total = len([t for t in transactions if t.status is not TransactionStatus.CAPTURED]) or 1
    groups: dict[tuple[FailureReason, PaymentMethod], list[Transaction]] = defaultdict(list)
    for t in failed:
        assert t.reason is not None
        groups[(t.reason, t.method)].append(t)

    cfg = policy.incidents
    span = timedelta(minutes=cfg.window_minutes)
    incidents: list[Incident] = []
    for (reason, method), txns in groups.items():
        if len(txns) < cfg.min_events:
            continue
        times = sorted(t.created_at for t in txns)
        # largest count of events falling inside any window-sized span
        concentrated = _max_in_window(list(times), span)
        if concentrated < cfg.min_events:
            continue
        share = concentrated / total
        if share >= cfg.share_threshold:
            incidents.append(
                Incident(
                    reason=reason,
                    method=method,
                    count=concentrated,
                    share=share,
                    window_minutes=cfg.window_minutes,
                )
            )
    return incidents


def _max_in_window(sorted_times: list[datetime], span: timedelta) -> int:
    best = 0
    left = 0
    for right in range(len(sorted_times)):
        while sorted_times[right] - sorted_times[left] > span:
            left += 1
        best = max(best, right - left + 1)
    return best
