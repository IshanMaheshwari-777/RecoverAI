"""The output of the diagnosis layer: one plain-English cause + one action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from revenue_recovery.domain.enums import DiagnosisAction, DiagnosisMethod


class Diagnosis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    root_cause: str
    action: DiagnosisAction
    method: DiagnosisMethod
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    model_name: str | None = None  # which LLM, when method == LLM
    latency_ms: int | None = None  # LLM round-trip, when applicable

    @property
    def is_ai_assisted(self) -> bool:
        return self.method in (DiagnosisMethod.LLM, DiagnosisMethod.LLM_FALLBACK)
