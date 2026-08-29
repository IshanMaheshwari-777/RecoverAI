"""Pipeline: diagnose -> decide -> execute, per transaction, with containment.

Three phases, so the LLM and payment-gateway calls run concurrently
instead of one-at-a-time (a 180-txn batch with a live LLM drops from ~100s
to ~5s):

  1. diagnose  -- parallel; each transaction is independent
  2. decide    -- SEQUENTIAL, in chronological order, because the recovery
                  engine carries a real per-customer contact history that
                  must see events in the order they happened
  3. execute   -- parallel again

If any phase raises for a given transaction, the error is caught, logged
in full, recorded as a failed `TransactionResult`, and the batch
continues -- one malformed record cannot take down the run.
"""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from recover_ai.config import Settings
from recover_ai.domain.audit import AuditLogEntry
from recover_ai.domain.enums import (
    DiagnosisAction,
    DiagnosisMethod,
    ErrorSource,
    ExecutionMethod,
    FailureReason,
    PaymentMethod,
    RecoveryOutcome,
    TransactionStatus,
)
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money
from recover_ai.domain.recovery import RecoveryDecision
from recover_ai.domain.results import PipelineReport, TransactionResult
from recover_ai.logging import get_logger
from recover_ai.ports.llm import LLMPort
from recover_ai.ports.payments import PaymentGatewayPort
from recover_ai.services.diagnosis import DiagnosisEngine
from recover_ai.services.execution import Executor
from recover_ai.services.recovery import RecoveryEngine

log = get_logger(__name__)

_T = TypeVar("_T")


def _fmt_exc(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"


def _concurrent(
    fn: Callable[[Transaction], _T],
    txns: Iterable[Transaction],
    *,
    max_workers: int,
) -> tuple[dict[str, _T], dict[str, str]]:
    """Run `fn` over each transaction on a thread pool. Returns (ok, errors)
    keyed by transaction id; a raise for one txn never affects the others."""
    ok: dict[str, _T] = {}
    err: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn, t): t.id for t in txns}
        for fut in as_completed(futures):
            tid = futures[fut]
            try:
                ok[tid] = fut.result()
            except Exception as exc:  # noqa: BLE001 -- this IS the containment boundary
                err[tid] = _fmt_exc(exc)
    return ok, err


@dataclass(slots=True)
class Pipeline:
    settings: Settings
    llm: LLMPort
    gateway: PaymentGatewayPort
    max_workers: int = 16

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

        decisions: dict[str, RecoveryDecision] = {}
        errors: dict[str, str] = {}
        by_id = {t.id: t for t in ordered}

        # phase 1 -- diagnose, concurrently
        diagnoses, diag_errors = _concurrent(
            diagnoser.diagnose, ordered, max_workers=self.max_workers
        )
        errors.update(diag_errors)

        # phase 2 -- decide, strictly in chronological order (stateful engine)
        for txn in ordered:
            if txn.id in errors:
                continue
            try:
                decisions[txn.id] = engine.decide(txn, diagnoses[txn.id])
            except Exception as exc:  # noqa: BLE001
                errors[txn.id] = _fmt_exc(exc)

        # phase 3 -- execute, concurrently
        entries, exec_errors = _concurrent(
            lambda t: executor.execute(t, decisions[t.id], diagnoses[t.id]),
            (by_id[tid] for tid in decisions),
            max_workers=self.max_workers,
        )
        errors.update(exec_errors)

        # assemble, back in chronological order
        results: list[TransactionResult] = []
        for txn in ordered:
            if txn.id in errors:
                log.error("pipeline_txn_failed", txn=txn.id, error=errors[txn.id].splitlines()[0])
                results.append(
                    TransactionResult(
                        transaction_id=txn.id,
                        stage_reached="failed",
                        audit_entry=_error_entry(txn, errors[txn.id]),
                        error=errors[txn.id],
                    )
                )
            else:
                results.append(
                    TransactionResult(
                        transaction_id=txn.id,
                        stage_reached="completed",
                        diagnosis=diagnoses[txn.id],
                        decision=decisions[txn.id],
                        audit_entry=entries[txn.id],
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


def _error_entry(txn: Transaction, error: str) -> AuditLogEntry:
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
        reason=error.splitlines()[0],
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
