"""Recovery layer: turn a diagnosis into a bounded, compliant decision.

The hard limits, enforced in code (not just documented):

  1. `do_not_contact` from the diagnosis is absolute. No branch below can
     turn it into an action.
  2. Retries are capped per transaction, per method. Once attempts reach
     the method's cap we stop retrying that rail and escalate to asking
     the customer to update / switch method instead.
  3. Contact is capped per customer: at most 2 messages (reminder or
     update request) to one person in a rolling 48 hours, across all
     their transactions. Automated retries never count -- only messages
     to a human do.

The batch is processed in chronological order, and the engine carries a
real per-customer contact history, so rule 3 is genuinely path-dependent
-- evaluated against prior activity the way it would be on a live stream.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from recover_ai.domain.diagnosis import Diagnosis
from recover_ai.domain.enums import CONTACT_ACTIONS, RETRY_ACTIONS, DiagnosisAction, FailureReason
from recover_ai.domain.models import Transaction
from recover_ai.domain.policy import Policy
from recover_ai.domain.recovery import RecoveryDecision
from recover_ai.services.strategies import retry_delay, strategy_for

# Retained for backwards compatibility; the live values come from Policy.
MAX_CONTACTS_PER_CUSTOMER_WINDOW = 2
CONTACT_WINDOW = timedelta(hours=48)

# (reason, method) pairs whose rail is currently degraded -- retries against
# them are deferred rather than piled onto a struggling gateway.
RailKey = tuple[FailureReason, str]


class RecoveryEngine:
    def __init__(
        self,
        policy: Policy | None = None,
        *,
        retry_hold_rails: Callable[[Transaction], bool] | None = None,
    ) -> None:
        self._policy = policy or Policy()
        self._cap = self._policy.contact_cap_per_window
        self._window = timedelta(hours=self._policy.contact_window_hours)
        self._retry_hold = retry_hold_rails or (lambda _t: False)
        self._contact_log: dict[str, list[datetime]] = {}

    # -- contact cap bookkeeping ------------------------------------------
    def _recent_contacts(self, customer_id: str, at: datetime) -> int:
        cutoff = at - self._window
        return sum(1 for t in self._contact_log.get(customer_id, []) if t >= cutoff)

    def _within_contact_cap(self, customer_id: str, at: datetime) -> bool:
        return self._recent_contacts(customer_id, at) < self._cap

    def _record_contact(self, customer_id: str, at: datetime) -> None:
        self._contact_log.setdefault(customer_id, []).append(at)

    # -- the decision --------------------------------------------------
    def decide(self, txn: Transaction, diagnosis: Diagnosis) -> RecoveryDecision:
        at = txn.created_at
        strat = strategy_for(txn.method)

        # Rule 1 -- compliance stop, absolute.
        if diagnosis.action is DiagnosisAction.DO_NOT_CONTACT:
            return self._blocked(
                txn,
                diagnosis,
                strat.name,
                "Diagnosis flagged do_not_contact -- honoured as-is, no override permitted.",
            )

        # Rule 2 -- retries capped per transaction / method.
        if diagnosis.action in RETRY_ACTIONS:
            if self._retry_hold(txn):
                return RecoveryDecision(
                    transaction_id=txn.id,
                    customer_id=txn.customer_id,
                    diagnosis_action=diagnosis.action,
                    final_action=None,
                    blocked=True,
                    held_for_incident=True,
                    reason=(
                        f"The {txn.method.value} rail is degraded right now "
                        "(incident detected in this batch) -- retry deferred, not abandoned."
                    ),
                    strategy=strat.name,
                )
            if txn.attempt_number >= strat.max_retries:
                if not self._within_contact_cap(txn.customer_id, at):
                    return self._blocked_by_contact_cap(txn, diagnosis, strat.name)
                self._record_contact(txn.customer_id, at)
                return RecoveryDecision(
                    transaction_id=txn.id,
                    customer_id=txn.customer_id,
                    diagnosis_action=diagnosis.action,
                    final_action=DiagnosisAction.REQUEST_UPDATE,
                    blocked=False,
                    reason=(
                        f"At attempt {txn.attempt_number} (cap {strat.max_retries} for "
                        f"{strat.name}) -- escalated to request_update; {strat.escalation_hint()}."
                    ),
                    strategy=strat.name,
                )

            scheduled_for = (
                at
                if diagnosis.action is DiagnosisAction.RETRY_NOW
                else at + retry_delay(txn.method, txn.reason, txn.attempt_number)
            )
            return RecoveryDecision(
                transaction_id=txn.id,
                customer_id=txn.customer_id,
                diagnosis_action=diagnosis.action,
                final_action=diagnosis.action,
                blocked=False,
                reason=(
                    "Within retry cap -- proceeding as diagnosed. Retries are silent; "
                    "nobody is being messaged, so the contact cap is untouched."
                ),
                strategy=strat.name,
                scheduled_for=scheduled_for,
            )

        # Rule 3 -- reminders / update requests capped per customer per window.
        if diagnosis.action in CONTACT_ACTIONS:
            if not self._within_contact_cap(txn.customer_id, at):
                return self._blocked_by_contact_cap(txn, diagnosis, strat.name)
            self._record_contact(txn.customer_id, at)
            return RecoveryDecision(
                transaction_id=txn.id,
                customer_id=txn.customer_id,
                diagnosis_action=diagnosis.action,
                final_action=diagnosis.action,
                blocked=False,
                reason="Within the per-customer contact cap -- proceeding as diagnosed.",
                strategy=strat.name,
            )

        return self._blocked(
            txn,
            diagnosis,
            strat.name,
            f"Unrecognised diagnosis action '{diagnosis.action}' -- blocked rather than guessed.",
        )

    # -- decision builders -------------------------------------------
    @staticmethod
    def _blocked(
        txn: Transaction, diagnosis: Diagnosis, strategy: str, reason: str
    ) -> RecoveryDecision:
        return RecoveryDecision(
            transaction_id=txn.id,
            customer_id=txn.customer_id,
            diagnosis_action=diagnosis.action,
            final_action=None,
            blocked=True,
            reason=reason,
            strategy=strategy,
        )

    def _blocked_by_contact_cap(
        self, txn: Transaction, diagnosis: Diagnosis, strategy: str
    ) -> RecoveryDecision:
        return self._blocked(
            txn,
            diagnosis,
            strategy,
            f"Customer already contacted {self._cap}+ times in the last "
            f"{self._policy.contact_window_hours}h -- holding off to avoid spamming them.",
        )


def decide_batch(
    engine: RecoveryEngine,
    pairs: list[tuple[Transaction, Diagnosis]],
) -> list[RecoveryDecision]:
    ordered = sorted(pairs, key=lambda p: p[0].created_at)
    return [engine.decide(txn, diag) for txn, diag in ordered]
