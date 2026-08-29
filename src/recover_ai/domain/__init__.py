"""Pure domain layer: entities, value objects, enums, errors. No I/O."""

from recover_ai.domain.audit import AuditLogEntry
from recover_ai.domain.diagnosis import Diagnosis
from recover_ai.domain.enums import (
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
from recover_ai.domain.errors import (
    LLMUnavailableError,
    NothingToDiagnoseError,
    PaymentGatewayError,
    PaymentGatewayRateLimitedError,
    RevenueRecoveryError,
)
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money
from recover_ai.domain.recovery import RecoveryDecision
from recover_ai.domain.results import (
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
