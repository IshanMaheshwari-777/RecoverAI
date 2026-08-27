"""Core entities: a Razorpay-shaped transaction and its error object.

Every stage of the pipeline reads and writes these shapes, so they live
in one place. They are strict Pydantic models -- malformed input is
rejected at the boundary, not three layers deep. (The failure-containment
demo deliberately smuggles one invalid record *past* this boundary with
`Transaction.model_construct`, to prove the pipeline still contains it.)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from revenue_recovery.domain.enums import (
    ErrorSource,
    FailureReason,
    PaymentMethod,
    TransactionStatus,
)
from revenue_recovery.domain.money import Money


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ErrorDetail(_Frozen):
    """Mirrors Razorpay's payment `error` object."""

    code: str
    description: str
    source: ErrorSource
    step: str
    reason: FailureReason
    field: str | None = None

    @classmethod
    def coerce_reason(cls, raw: str) -> FailureReason:
        try:
            return FailureReason(raw)
        except ValueError:
            return FailureReason.UNKNOWN


class Transaction(_Frozen):
    id: str
    order_id: str
    customer_id: str
    amount: Money
    method: PaymentMethod
    status: TransactionStatus
    created_at: datetime
    attempt_number: int = Field(default=1, ge=1)
    error: ErrorDetail | None = None

    @property
    def needs_attention(self) -> bool:
        return self.status is not TransactionStatus.CAPTURED

    @property
    def reason(self) -> FailureReason | None:
        return self.error.reason if self.error else None
