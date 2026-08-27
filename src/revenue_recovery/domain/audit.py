"""The immutable record of what the agent did to one transaction.

One entry per decision -- executed, blocked, or crashed. An audit trail
that only records successes is not an audit trail.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from revenue_recovery.domain.enums import (
    DiagnosisAction,
    DiagnosisMethod,
    ExecutionMethod,
    RecoveryOutcome,
)
from revenue_recovery.domain.money import Money


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    customer_id: str
    amount: Money
    diagnosis_method: DiagnosisMethod
    diagnosis_action: DiagnosisAction
    final_action: DiagnosisAction | None
    executed: bool
    execution_method: ExecutionMethod
    projected_outcome: RecoveryOutcome
    confirmed_outcome: RecoveryOutcome = RecoveryOutcome.PENDING
    detail: str
    reason: str
    payment_link_id: str | None = None
    scheduled_for: datetime | None = None
    recorded_at: datetime = Field(default_factory=datetime.now)

    @property
    def recovered_amount(self) -> Money:
        """Revenue we project as recovered (0 unless the action landed)."""
        if self.executed and self.projected_outcome is RecoveryOutcome.RECOVERED:
            return self.amount
        return Money.zero()
