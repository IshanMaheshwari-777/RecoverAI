"""Execution layer: carry out a recovery decision, record an audit entry.

  retry_now / retry_later  -> create a fresh payment link (you cannot
                              silently re-charge a declined card)
  send_reminder / request_update -> draft a customer message (LLM, or a
                              plain template when no LLM is configured)
  blocked / unhandled      -> execute nothing, but still write an entry

Every path returns exactly one `AuditLogEntry`. Nothing here decides
whether money moves -- that was settled by the recovery layer.
"""

from __future__ import annotations

from revenue_recovery.domain.audit import AuditLogEntry
from revenue_recovery.domain.diagnosis import Diagnosis
from revenue_recovery.domain.enums import (
    DiagnosisAction,
    ExecutionMethod,
    RecoveryOutcome,
)
from revenue_recovery.domain.errors import LLMUnavailableError
from revenue_recovery.domain.models import Transaction
from revenue_recovery.domain.recovery import RecoveryDecision
from revenue_recovery.logging import get_logger
from revenue_recovery.ports.llm import LLMPort
from revenue_recovery.ports.payments import PaymentGatewayPort
from revenue_recovery.services.outcomes import project_outcome

log = get_logger(__name__)

_MESSAGE_PROMPT = """\
Write a short, friendly customer message (2-3 sentences, no emoji) for a payment
recovery nudge.

Context:
- reason: {cause}
- amount: {amount}
- what we're asking the customer to do: {ask}

Keep it low-pressure and helpful, not pushy. Reply with only the message text.
"""


class Executor:
    def __init__(self, gateway: PaymentGatewayPort, llm: LLMPort) -> None:
        self._gateway = gateway
        self._llm = llm

    def execute(
        self, txn: Transaction, decision: RecoveryDecision, diagnosis: Diagnosis
    ) -> AuditLogEntry:
        if decision.blocked or decision.final_action is None:
            return self._entry(
                txn,
                decision,
                diagnosis,
                executed=False,
                method=ExecutionMethod.BLOCKED,
                projected=RecoveryOutcome.NOT_APPLICABLE,
                detail="No action taken.",
            )

        action = decision.final_action
        if action in (DiagnosisAction.RETRY_NOW, DiagnosisAction.RETRY_LATER):
            return self._retry(txn, decision, diagnosis, action)
        if action in (DiagnosisAction.SEND_REMINDER, DiagnosisAction.REQUEST_UPDATE):
            return self._message(txn, decision, diagnosis, action)

        return self._entry(
            txn,
            decision,
            diagnosis,
            executed=False,
            method=ExecutionMethod.UNHANDLED,
            projected=RecoveryOutcome.NOT_APPLICABLE,
            detail=f"Unrecognised action {action!r} -- not executed.",
        )

    # -- action handlers --------------------------------------------
    def _retry(
        self,
        txn: Transaction,
        decision: RecoveryDecision,
        diagnosis: Diagnosis,
        action: DiagnosisAction,
    ) -> AuditLogEntry:
        link = self._gateway.create_payment_link(
            amount=txn.amount,
            order_id=txn.order_id,
            description=f"Complete your payment for order {txn.order_id}",
            note=diagnosis.root_cause,
        )
        when = (
            "now"
            if action is DiagnosisAction.RETRY_NOW
            else f"scheduled for {decision.scheduled_for:%Y-%m-%d %H:%M UTC}"
        )
        kind = "Order" if link.method is ExecutionMethod.RAZORPAY_ORDER else "Payment link"
        return self._entry(
            txn,
            decision,
            diagnosis,
            executed=True,
            method=link.method,
            projected=project_outcome(action, txn.id),
            detail=f"{kind} {link.id} ({link.short_url}) -- retry {when}.",
            payment_link_id=link.id,
        )

    def _message(
        self,
        txn: Transaction,
        decision: RecoveryDecision,
        diagnosis: Diagnosis,
        action: DiagnosisAction,
    ) -> AuditLogEntry:
        text, method = self._draft_message(txn, diagnosis, action)
        return self._entry(
            txn,
            decision,
            diagnosis,
            executed=True,
            method=method,
            projected=project_outcome(action, txn.id),
            detail=text,
        )

    def _draft_message(
        self, txn: Transaction, diagnosis: Diagnosis, action: DiagnosisAction
    ) -> tuple[str, ExecutionMethod]:
        ask = (
            "update or switch their payment method"
            if action is DiagnosisAction.REQUEST_UPDATE
            else "complete the pending payment"
        )
        try:
            reply = self._llm.complete(
                _MESSAGE_PROMPT.format(
                    cause=diagnosis.root_cause, amount=txn.amount.format(), ask=ask
                ),
                max_tokens=300,
            )
            return reply.text, ExecutionMethod.LLM_MESSAGE
        except LLMUnavailableError:
            return _template_message(txn, action), ExecutionMethod.TEMPLATE_MESSAGE

    # -- entry builder ---------------------------------------------
    @staticmethod
    def _entry(
        txn: Transaction,
        decision: RecoveryDecision,
        diagnosis: Diagnosis,
        *,
        executed: bool,
        method: ExecutionMethod,
        projected: RecoveryOutcome,
        detail: str,
        payment_link_id: str | None = None,
    ) -> AuditLogEntry:
        confirmed = RecoveryOutcome.PENDING if executed else RecoveryOutcome.NOT_APPLICABLE
        return AuditLogEntry(
            transaction_id=txn.id,
            customer_id=txn.customer_id,
            amount=txn.amount,
            diagnosis_method=diagnosis.method,
            diagnosis_action=decision.diagnosis_action,
            final_action=decision.final_action,
            executed=executed,
            execution_method=method,
            projected_outcome=projected,
            confirmed_outcome=confirmed,
            detail=detail,
            reason=decision.reason,
            payment_link_id=payment_link_id,
            scheduled_for=decision.scheduled_for,
        )


def _template_message(txn: Transaction, action: DiagnosisAction) -> str:
    if action is DiagnosisAction.REQUEST_UPDATE:
        return (
            f"Hi -- your recent payment of {txn.amount.format()} didn't go through. "
            "Could you update your payment method and try again? Happy to help if you're stuck."
        )
    return (
        f"Hi -- looks like your order for {txn.amount.format()} wasn't completed. "
        "No rush; here's a link to finish whenever you're ready."
    )
