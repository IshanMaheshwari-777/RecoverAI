"""Pipeline: diagnose -> decide -> execute, per transaction, with containment.

Transactions are processed in chronological order so the recovery
engine's per-customer contact history is genuine. If any stage raises for
a given transaction, the error is caught, logged in full, recorded as a
failed `TransactionResult` with its own audit entry, and the batch
continues -- one malformed record cannot take down the run.
"""

from __future__ import annotations

import traceback
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from revenue_recovery.config import Settings
from revenue_recovery.domain.audit import AuditLogEntry
from revenue_recovery.domain.enums import (
    DiagnosisAction,
    DiagnosisMethod,
    ErrorSource,
    ExecutionMethod,
    FailureReason,
    PaymentMethod,
    RecoveryOutcome,
    TransactionStatus,
)
from revenue_recovery.domain.models import ErrorDetail, Transaction
from revenue_recovery.domain.money import Money
from revenue_recovery.domain.results import PipelineReport, TransactionResult
from revenue_recovery.logging import get_logger
from revenue_recovery.ports.llm import LLMPort
from revenue_recovery.ports.payments import PaymentGatewayPort
from revenue_recovery.services.diagnosis import DiagnosisEngine
from revenue_recovery.services.execution import Executor
from revenue_recovery.services.recovery import RecoveryEngine

log = get_logger(__name__)


@dataclass(slots=True)
class Pipeline:
    settings: Settings
    llm: LLMPort
    gateway: PaymentGatewayPort

    def run(
        self,
        transactions: list[Transaction],
        *,
        seed: int,
        count: int,
        failure_injected: bool = False,
    ) -> PipelineReport:
        started = datetime.now(tz=UTC)
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        log.info("pipeline_start", run_id=run_id, transactions=len(transactions))

        diagnoser = DiagnosisEngine(self.llm)
        engine = RecoveryEngine()
        executor = Executor(self.gateway, self.llm)

        ordered = sorted(
            (t for t in transactions if t.status is not TransactionStatus.CAPTURED),
            key=lambda t: t.created_at,
        )

        results: list[TransactionResult] = []
        for txn in ordered:
            try:
                diagnosis = diagnoser.diagnose(txn)
                decision = engine.decide(txn, diagnosis)
                entry = executor.execute(txn, decision, diagnosis)
                results.append(
                    TransactionResult(
                        transaction_id=txn.id,
                        stage_reached="completed",
                        diagnosis=diagnosis,
                        decision=decision,
                        audit_entry=entry,
                    )
                )
            except Exception as exc:  # noqa: BLE001 -- this IS the containment boundary
                log.error("pipeline_txn_failed", txn=txn.id, error=repr(exc))
                results.append(
                    TransactionResult(
                        transaction_id=txn.id,
                        stage_reached="failed",
                        audit_entry=_error_entry(txn, exc),
                        error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}",
                    )
                )

        finished = datetime.now(tz=UTC)
        summary = PipelineReport.summarise(total_transactions=len(transactions), results=results)
        log.info(
            "pipeline_done",
            run_id=run_id,
            completed=summary.completed,
            failed=summary.failed,
            projected_recovered=str(summary.projected_recovered),
        )
        return PipelineReport(
            run_id=run_id,
            seed=seed,
            count=count,
            failure_injected=failure_injected,
            started_at=started,
            finished_at=finished,
            razorpay_live=self.gateway.live,
            anthropic_live=self.llm.available,
            llm_model=self.llm.model if self.llm.available else None,
            results=results,
            summary=summary,
        )


def _error_entry(txn: Transaction, exc: Exception) -> AuditLogEntry:
    return AuditLogEntry(
        transaction_id=txn.id,
        customer_id=getattr(txn, "customer_id", "unknown"),
        amount=Money.zero(),
        diagnosis_method=DiagnosisMethod.UNHANDLED,
        diagnosis_action=DiagnosisAction.DO_NOT_CONTACT,
        final_action=None,
        executed=False,
        execution_method=ExecutionMethod.PIPELINE_ERROR,
        projected_outcome=RecoveryOutcome.NOT_APPLICABLE,
        confirmed_outcome=RecoveryOutcome.NOT_APPLICABLE,
        detail="Processing failed -- flagged for manual review, amount unverified.",
        reason=f"{type(exc).__name__}: {exc}",
    )


def inject_poison_transaction(transactions: list[Transaction]) -> list[Transaction]:
    """Append one record that is invalid in a way our domain model would
    normally reject at ingestion -- a non-numeric amount -- to prove the
    containment boundary holds against data that slipped past validation
    (a legacy export, a bad migration). `model_construct` skips validation
    on purpose. The reason is set to `network_issue` (a rule-based
    auto-retry case) so the record reaches the executor's payment-link
    path, where formatting the bad amount raises -- deterministically.
    """
    poisoned = Transaction.model_construct(
        id="pay_POISONED_DEMO",
        order_id="order_POISONED_DEMO",
        customer_id="cust_POISONED_DEMO",
        amount="not-a-number",  # type: ignore[arg-type]
        method=PaymentMethod.CARD,
        status=TransactionStatus.FAILED,
        created_at=datetime.now(tz=UTC),
        attempt_number=1,
        error=ErrorDetail(
            code="SERVER_ERROR",
            description="Network connectivity issue during payment processing",
            source=ErrorSource.NETWORK,
            step="payment_authorization",
            reason=FailureReason.NETWORK_ISSUE,
        ),
    )
    return [*transactions, poisoned]
