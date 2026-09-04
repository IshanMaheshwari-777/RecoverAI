"""In-process holder for the current pipeline report.

The report lives on disk (data/pipeline_report.json); this wraps it with
a lock and the mutations the API needs -- running a fresh pipeline, and
applying a webhook confirmation. A `payment_link.paid` webhook does two
things: it flips the audit entry's *confirmed* outcome, and it feeds the
learning loop a real, labelled observation so the conversion posteriors
move toward reality. It is deliberately simple -- a real deployment puts
runs in a database and a queue.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from recover_ai.app import load_report, run_pipeline, save_report
from recover_ai.config import get_settings
from recover_ai.domain.enums import FailureReason, RecoveryOutcome
from recover_ai.domain.policy import Policy
from recover_ai.domain.results import PipelineReport, TransactionResult
from recover_ai.logging import get_logger
from recover_ai.services.learning import load_learning, save_learning

log = get_logger(__name__)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _reason_from_key(key: str) -> FailureReason | None:
    parts = key.split("|")
    if len(parts) < 3:
        return None
    try:
        return FailureReason(parts[2])
    except ValueError:
        return None


class ReportStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._report: PipelineReport | None = load_report()

    @property
    def report(self) -> PipelineReport | None:
        return self._report

    def run(
        self,
        *,
        count: int,
        seed: int,
        inject_failure: bool,
        mode: str = "live",
        source: str = "synthetic",
    ) -> PipelineReport:
        with self._lock:
            report = run_pipeline(
                count=count,
                seed=seed,
                inject_failure=inject_failure,
                mode=mode,
                source=source,  # type: ignore[arg-type]
            )
            if mode == "live":
                save_report(report)
            self._report = report
            return report

    def confirm_payment(self, payment_link_id: str) -> TransactionResult | None:
        """A `payment_link.paid` webhook: mark the entry confirmed and feed
        the learning loop the real outcome."""
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

            self._observe(updated, converted=True)

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

    @staticmethod
    def _observe(result: TransactionResult, *, converted: bool) -> None:
        entry = result.audit_entry
        if not entry.conversion_key:
            return
        settings = get_settings()
        policy = Policy.load(settings.data_dir)
        learning = load_learning(policy, settings.data_dir)
        learning.observe_conversion(
            entry.conversion_key, converted=converted, predicted=entry.predicted_rate
        )

        # a paid retry landed -- feed the timing model how long it took
        if converted and entry.payment_link_id and entry.recorded_at is not None:
            reason = _reason_from_key(entry.conversion_key)
            hours = (datetime.now(UTC) - _as_utc(entry.recorded_at)).total_seconds() / 3600
            learning.observe_retry_landing(reason, min(max(hours, 0.05), 72.0))

        save_learning(learning, settings.data_dir)


store = ReportStore()


def ensure_seed_report() -> PipelineReport:
    """Guarantee there is a report to show (used on first API boot)."""
    if store.report is None:
        get_settings()
        store.run(count=180, seed=42, inject_failure=False)
    assert store.report is not None
    return store.report
