"""Pipeline output and the aggregate report the API/UI consume."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from recover_ai.domain.audit import AuditLogEntry
from recover_ai.domain.diagnosis import Diagnosis
from recover_ai.domain.enums import ExecutionMethod, RecoveryOutcome
from recover_ai.domain.money import Money
from recover_ai.domain.recovery import RecoveryDecision


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


class CausalLift(BaseModel):
    """Treatment vs. an untouched holdout control -- true incremental lift,
    not a projection. In the batch demo both sides use the same seeded
    conversion model, so the number is illustrative; in production the
    control's conversions are real webhook events."""

    holdout_fraction: float = 0.0
    treatment_n: int = 0
    control_n: int = 0
    treatment_rate: float = 0.0
    control_rate: float = 0.0

    @property
    def incremental_rate(self) -> float:
        return max(0.0, self.treatment_rate - self.control_rate)


class Economics(BaseModel):
    """What the recovery run cost and what its expected value was."""

    total_channel_cost: float = 0.0
    net_expected_value: float = 0.0
    skipped_negative_ev: int = 0
    positive_ev_actions: int = 0
    channel_mix: dict[str, int] = Field(default_factory=dict)


class RunSummary(BaseModel):
    """The headline numbers. Everything here is derived, never stored twice."""

    total_transactions: int
    needing_attention: int
    completed: int
    failed: int
    executed_actions: int
    blocked_actions: int
    escalated_actions: int
    held_out_actions: int = 0
    retries_held_incident: int = 0
    at_risk: Money
    projected_recovered: Money
    confirmed_recovered: Money
    recovery_rate: float
    compliance_violations: int
    diagnosis_split: DiagnosisSplit
    execution_methods: dict[str, int]
    action_breakdown: dict[str, int]
    causal: CausalLift = Field(default_factory=CausalLift)
    economics: Economics = Field(default_factory=Economics)


class IncidentRecord(BaseModel):
    reason: str
    method: str
    count: int
    share: float
    window_minutes: int
    action_taken: str


class PipelineReport(BaseModel):
    """The single object the API serves and the SPA renders."""

    # `extra="ignore"` (not "forbid") so the model round-trips its own
    # serialised form -- computed fields like `duration_ms` come back as input.
    model_config = ConfigDict(extra="ignore")

    run_id: str
    seed: int
    count: int
    failure_injected: bool
    mode: str = "live"  # "live" | "shadow"
    policy_version: str = "builtin/1"
    started_at: datetime
    finished_at: datetime
    razorpay_live: bool
    anthropic_live: bool
    llm_model: str | None
    results: list[TransactionResult] = Field(default_factory=list)
    summary: RunSummary
    incidents: list[IncidentRecord] = Field(default_factory=list)
    learning: dict[str, object] | None = None

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
        confirmed = sum((e.confirmed_amount for e in executed), Money.zero())
        violations = sum(
            1
            for r in completed
            if r.decision
            and r.diagnosis
            and r.diagnosis.action.value == "do_not_contact"
            and r.decision.final_action is not None
        )

        held_out = [e for e in entries if e.held_out]
        retries_held = [
            e for e in entries if e.execution_method is ExecutionMethod.RETRY_HELD_INCIDENT
        ]
        skipped_ev = [
            e for e in entries if e.execution_method is ExecutionMethod.SKIPPED_NEGATIVE_EV
        ]

        return RunSummary(
            total_transactions=total_transactions,
            needing_attention=len(results),
            completed=len(completed),
            failed=len(failed),
            executed_actions=len(executed),
            blocked_actions=len(entries) - len(executed) - len(held_out),
            escalated_actions=sum(1 for r in completed if r.decision and r.decision.escalated),
            held_out_actions=len(held_out),
            retries_held_incident=len(retries_held),
            at_risk=at_risk,
            projected_recovered=projected,
            confirmed_recovered=confirmed,
            recovery_rate=projected.ratio(at_risk),
            compliance_violations=violations,
            diagnosis_split=split,
            execution_methods=dict(Counter(e.execution_method.value for e in entries)),
            action_breakdown=dict(Counter(e.final_action.value for e in entries if e.final_action)),
            causal=_causal_lift(entries),
            economics=_economics(entries, skipped_ev),
        )


def _causal_lift(entries: list[AuditLogEntry]) -> CausalLift:
    treatment = [e for e in entries if e.executed and not e.held_out]
    control = [e for e in entries if e.held_out]
    if not control:
        return CausalLift()

    def rate(rows: list[AuditLogEntry]) -> float:
        if not rows:
            return 0.0
        hits = sum(
            1
            for e in rows
            if e.projected_outcome is RecoveryOutcome.RECOVERED
            or e.confirmed_outcome is RecoveryOutcome.RECOVERED
        )
        return hits / len(rows)

    frac = len(control) / (len(control) + len(treatment)) if (control or treatment) else 0.0
    return CausalLift(
        holdout_fraction=round(frac, 3),
        treatment_n=len(treatment),
        control_n=len(control),
        treatment_rate=round(rate(treatment), 4),
        control_rate=round(rate(control), 4),
    )


def _economics(entries: list[AuditLogEntry], skipped_ev: list[AuditLogEntry]) -> Economics:
    acted = [e for e in entries if e.executed]
    total_cost = sum(e.channel_cost or 0.0 for e in acted)
    total_nev = sum(e.net_expected_value or 0.0 for e in acted)
    mix = Counter(e.channel.value for e in acted if e.channel is not None)
    return Economics(
        total_channel_cost=round(total_cost, 2),
        net_expected_value=round(total_nev, 2),
        skipped_negative_ev=len(skipped_ev),
        positive_ev_actions=len(acted),
        channel_mix=dict(mix),
    )
