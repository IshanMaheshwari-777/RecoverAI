"""Pipeline output and the aggregate report the API/UI consume."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from revenue_recovery.domain.audit import AuditLogEntry
from revenue_recovery.domain.diagnosis import Diagnosis
from revenue_recovery.domain.enums import RecoveryOutcome
from revenue_recovery.domain.money import Money
from revenue_recovery.domain.recovery import RecoveryDecision


class TransactionResult(BaseModel):
    """Everything that happened to one transaction in one pipeline run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    stage_reached: str  # "completed" | "failed"
    diagnosis: Diagnosis | None = None
    decision: RecoveryDecision | None = None
    audit_entry: AuditLogEntry
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.stage_reached == "failed"


class DiagnosisSplit(BaseModel):
    rule: int = 0
    llm: int = 0
    llm_fallback: int = 0
    unhandled: int = 0

    @property
    def total(self) -> int:
        return self.rule + self.llm + self.llm_fallback + self.unhandled

    @property
    def rule_share(self) -> float:
        return self.rule / self.total if self.total else 0.0


class RunSummary(BaseModel):
    """The headline numbers. Everything here is derived, never stored twice."""

    total_transactions: int
    needing_attention: int
    completed: int
    failed: int
    executed_actions: int
    blocked_actions: int
    escalated_actions: int
    at_risk: Money
    projected_recovered: Money
    confirmed_recovered: Money
    recovery_rate: float
    compliance_violations: int
    diagnosis_split: DiagnosisSplit
    execution_methods: dict[str, int]
    action_breakdown: dict[str, int]


class PipelineReport(BaseModel):
    """The single object the API serves and the SPA renders."""

    # `extra="ignore"` (not "forbid") so the model round-trips its own
    # serialised form -- computed fields like `duration_ms` come back as input.
    model_config = ConfigDict(extra="ignore")

    run_id: str
    seed: int
    count: int
    failure_injected: bool
    started_at: datetime
    finished_at: datetime
    razorpay_live: bool
    anthropic_live: bool
    llm_model: str | None
    results: list[TransactionResult] = Field(default_factory=list)
    summary: RunSummary

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_ms(self) -> int:
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    @staticmethod
    def summarise(
        *,
        total_transactions: int,
        results: list[TransactionResult],
    ) -> RunSummary:
        completed = [r for r in results if not r.failed]
        failed = [r for r in results if r.failed]
        entries = [r.audit_entry for r in results]
        executed = [e for e in entries if e.executed]

        split = DiagnosisSplit()
        for r in completed:
            if r.diagnosis is not None:
                field = r.diagnosis.method.value
                setattr(split, field, getattr(split, field) + 1)

        at_risk = sum((e.amount for e in entries), Money.zero())
        projected = sum((e.recovered_amount for e in executed), Money.zero())
        confirmed = sum(
            (e.amount for e in executed if e.confirmed_outcome is RecoveryOutcome.RECOVERED),
            Money.zero(),
        )
        violations = sum(
            1
            for r in completed
            if r.decision
            and r.diagnosis
            and r.diagnosis.action.value == "do_not_contact"
            and r.decision.final_action is not None
        )

        return RunSummary(
            total_transactions=total_transactions,
            needing_attention=len(results),
            completed=len(completed),
            failed=len(failed),
            executed_actions=len(executed),
            blocked_actions=len(entries) - len(executed),
            escalated_actions=sum(1 for r in completed if r.decision and r.decision.escalated),
            at_risk=at_risk,
            projected_recovered=projected,
            confirmed_recovered=confirmed,
            recovery_rate=projected.ratio(at_risk),
            compliance_violations=violations,
            diagnosis_split=split,
            execution_methods=dict(Counter(e.execution_method.value for e in entries)),
            action_breakdown=dict(Counter(e.final_action.value for e in entries if e.final_action)),
        )
