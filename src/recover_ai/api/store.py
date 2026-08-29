"""In-process holder for the current pipeline report.

The report lives on disk (data/pipeline_report.json); this wraps it with
a lock and a couple of mutations the API needs (running a fresh pipeline,
applying a webhook confirmation). It is deliberately simple -- a real
deployment would put runs in a database and a queue.
"""

from __future__ import annotations

import threading

from recover_ai.app import load_report, run_pipeline, save_report
from recover_ai.config import get_settings
from recover_ai.domain.enums import RecoveryOutcome
from recover_ai.domain.results import PipelineReport, TransactionResult
from recover_ai.logging import get_logger

log = get_logger(__name__)


class ReportStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._report: PipelineReport | None = load_report()

    @property
    def report(self) -> PipelineReport | None:
        return self._report

    def run(self, *, count: int, seed: int, inject_failure: bool) -> PipelineReport:
        with self._lock:
            report = run_pipeline(count=count, seed=seed, inject_failure=inject_failure)
            save_report(report)
            self._report = report
            return report

    def confirm_payment(self, payment_link_id: str) -> TransactionResult | None:
        """Flip one audit entry's confirmed outcome to RECOVERED.

        This is what a real `payment_link.paid` webhook from Razorpay would
        drive -- turning a *projected* recovery into a *confirmed* one.
        """
        with self._lock:
            if self._report is None:
                return None
            updated: TransactionResult | None = None
            new_results = []
            for result in self._report.results:
                entry = result.audit_entry
                if entry.payment_link_id == payment_link_id and not updated:
                    entry = entry.model_copy(
                        update={"confirmed_outcome": RecoveryOutcome.RECOVERED}
                    )
                    result = result.model_copy(update={"audit_entry": entry})
                    updated = result
                new_results.append(result)

            if updated is None:
                return None

            summary = PipelineReport.summarise(
                total_transactions=self._report.summary.total_transactions,
                results=new_results,
            )
            self._report = self._report.model_copy(
                update={"results": new_results, "summary": summary}
            )
            save_report(self._report)
            log.info("webhook_confirmed", payment_link_id=payment_link_id)
            return updated


store = ReportStore()


def ensure_seed_report() -> PipelineReport:
    """Guarantee there is a report to show (used on first API boot)."""
    if store.report is None:
        get_settings()
        store.run(count=180, seed=42, inject_failure=False)
    assert store.report is not None
    return store.report
