"""Pure domain layer: entities, value objects, enums, errors. No I/O."""

from revenue_recovery.domain.audit import AuditLogEntry
from revenue_recovery.domain.diagnosis import Diagnosis
from revenue_recovery.domain.enums import (
    CONTACT_ACTIONS,
    RETRY_ACTIONS,
    DiagnosisAction,
    DiagnosisMethod,
    ErrorSource,
    ExecutionMethod,
    FailureReason,
    PaymentMethod,
    RecoveryOutcome,
    TransactionStatus,
)
from revenue_recovery.domain.errors import (
    LLMUnavailableError,
    NothingToDiagnoseError,
    PaymentGatewayError,
    PaymentGatewayRateLimitedError,
    RevenueRecoveryError,
)
from revenue_recovery.domain.models import ErrorDetail, Transaction
from revenue_recovery.domain.money import Money
from revenue_recovery.domain.recovery import RecoveryDecision
from revenue_recovery.domain.results import (
    DiagnosisSplit,
    PipelineReport,
    RunSummary,
    TransactionResult,
)

__all__ = [
    "CONTACT_ACTIONS",
    "RETRY_ACTIONS",
    "AuditLogEntry",
    "Diagnosis",
    "DiagnosisAction",
    "DiagnosisMethod",
    "DiagnosisSplit",
    "ErrorDetail",
    "ErrorSource",
    "ExecutionMethod",
    "FailureReason",
    "LLMUnavailableError",
    "Money",
    "NothingToDiagnoseError",
    "PaymentGatewayError",
    "PaymentGatewayRateLimitedError",
    "PaymentMethod",
    "PipelineReport",
    "RecoveryDecision",
    "RecoveryOutcome",
    "RevenueRecoveryError",
    "RunSummary",
    "Transaction",
    "TransactionResult",
    "TransactionStatus",
]
