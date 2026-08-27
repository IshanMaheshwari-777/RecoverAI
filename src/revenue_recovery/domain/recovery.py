"""The output of the recovery layer: a bounded, compliant decision.

`diagnosis_action` is what the diagnosis *recommended*; `final_action` is
what the stopping rules actually allow. When they differ (or `blocked` is
set) the `reason` explains why -- that gap is the whole point of the
layer and it must always be auditable.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from revenue_recovery.domain.enums import DiagnosisAction


class RecoveryDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    customer_id: str
    diagnosis_action: DiagnosisAction
    final_action: DiagnosisAction | None  # None == blocked, nothing runs
    blocked: bool
    reason: str
    strategy: str = "default"  # per-method playbook that was applied
    scheduled_for: datetime | None = None  # when a retry should fire (retry_later)

    @property
    def escalated(self) -> bool:
        return (
            not self.blocked
            and self.diagnosis_action in (DiagnosisAction.RETRY_NOW, DiagnosisAction.RETRY_LATER)
            and self.final_action == DiagnosisAction.REQUEST_UPDATE
        )
