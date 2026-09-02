"""Execution layer: carry out a recovery decision, record an audit entry.

  retry_now / retry_later  -> create a fresh payment link (you cannot
                              silently re-charge a declined card)
  send_reminder / request_update -> draft a customer message (LLM, or a
                              plain template when no LLM is configured),
                              on the cheapest deliverable channel
  blocked / unhandled      -> execute nothing, but still write an entry

Before acting, two gates:
  * expected value -- skip a recovery whose net expected value (after
    channel cost and chargeback / support risk) is below the policy floor
  * idempotency    -- a decision already executed in a prior run is not
    executed again; the earlier result stands

Every path returns exactly one `AuditLogEntry`. Nothing here decides
*whether* money moves -- the recovery layer settled that -- only how, and
whether it clears the economics.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from recover_ai.domain.audit import AuditLogEntry
from recover_ai.domain.diagnosis import Diagnosis
from recover_ai.domain.enums import (
    RETRY_ACTIONS,
    Channel,
    DiagnosisAction,
    ExecutionMethod,
    RecoveryOutcome,
)
from recover_ai.domain.errors import LLMUnavailableError
from recover_ai.domain.models import Transaction
from recover_ai.domain.policy import Policy
from recover_ai.domain.recovery import RecoveryDecision
from recover_ai.logging import get_logger
from recover_ai.ports.llm import LLMPort
from recover_ai.ports.payments import PaymentGatewayPort
from recover_ai.services.economics import EVResult, best_channel
from recover_ai.services.idempotency import IdempotencyStore, execution_key
from recover_ai.services.learning import LearningStore, conversion_key
from recover_ai.services.outcomes import prior_rate, project_outcome

log = get_logger(__name__)

_MESSAGE_PROMPT = """\
Write a short, friendly customer message for a payment recovery nudge, to be
sent over {channel}.

Context:
- reason: {cause}
- amount: {amount}
- what we're asking the customer to do: {ask}

{channel_hint} Keep it low-pressure and helpful, not pushy. Reply with only the
message text.
"""

_CHANNEL_HINT = {
    Channel.SMS: "Two sentences, no links spelled out.",
    Channel.WHATSAPP: "Two or three sentences, conversational.",
    Channel.EMAIL: "Three sentences; a subject line is not needed.",
    Channel.IN_APP: "One or two sentences; it shows as a notification.",
}


@dataclass(frozen=True, slots=True)
class _Meta:
    """Learning / economics fields common to every entry for one decision."""

    policy_version: str
    conversion_key: str
    predicted_rate: float
    net_expected_value: float
    channel: Channel
    channel_cost: float


class Executor:
    def __init__(
        self,
        gateway: PaymentGatewayPort,
        llm: LLMPort,
        *,
        learning: LearningStore | None = None,
        policy: Policy | None = None,
        idempotency: IdempotencyStore | None = None,
    ) -> None:
        self._gateway = gateway
        self._llm = llm
        self._policy = policy or Policy()
        self._learning = learning
        self._idem = idempotency

    # -- rate + channel -------------------------------------------
    def _rate_for(
        self, txn: Transaction, action: DiagnosisAction, amount: float
    ) -> tuple[str, float]:
        band = self._policy.amount_band(amount)
        key = conversion_key(action, txn.method, txn.reason, band)
        if self._learning is not None:
            return key, self._learning.rate(key)
        return key, prior_rate(action)

    def _deliverable(self, customer_id: str) -> Callable[[Channel], bool]:
        learning = self._learning

        def check(channel: Channel) -> bool:
            if learning is None:
                return True
            return learning.deliverable(customer_id, channel.value)

        return check

    # -- entry point ----------------------------------------------
    def execute(
        self,
        txn: Transaction,
        decision: RecoveryDecision,
        diagnosis: Diagnosis,
        *,
        held_out: bool = False,
        shadow: bool = False,
    ) -> AuditLogEntry:
        if decision.blocked or decision.final_action is None:
            method = (
                ExecutionMethod.RETRY_HELD_INCIDENT
                if decision.held_for_incident
                else ExecutionMethod.BLOCKED
            )
            return self._entry(
                txn,
                decision,
                diagnosis,
                executed=False,
                method=method,
                projected=RecoveryOutcome.NOT_APPLICABLE,
                detail="Retry deferred while the rail recovers."
                if decision.held_for_incident
                else "No action taken.",
            )

        action = decision.final_action
        try:
            amount = float(txn.amount.rupees)
        except AttributeError as exc:  # a record that slipped past validation
            raise ValueError(f"not a valid monetary amount: {txn.amount!r}") from exc
        key, rate = self._rate_for(txn, action, amount)
        ev: EVResult = best_channel(
            policy=self._policy,
            action=action,
            amount=amount,
            p_recover=rate,
            deliverable=self._deliverable(txn.customer_id),
        )
        meta = _Meta(
            policy_version=self._policy.version,
            conversion_key=key,
            predicted_rate=round(rate, 4),
            net_expected_value=ev.net_expected_value,
            channel=ev.channel,
            channel_cost=ev.channel_cost,
        )

        if held_out:
            # The control still has an outcome -- the customer may complete on
            # their own. Drawn at the organic rate so treatment vs. control is
            # a real comparison, not treatment vs. zero.
            return self._entry(
                txn,
                decision,
                diagnosis,
                executed=False,
                method=ExecutionMethod.HOLDOUT_CONTROL,
                projected=project_outcome(
                    rate=self._policy.organic_recovery_rate, transaction_id=txn.id
                ),
                detail="Held out as a causal control -- decided, deliberately not executed.",
                held_out=True,
                meta=meta,
            )
        if not ev.worth_pursuing:
            return self._entry(
                txn,
                decision,
                diagnosis,
                executed=False,
                method=ExecutionMethod.SKIPPED_NEGATIVE_EV,
                projected=RecoveryOutcome.NOT_APPLICABLE,
                detail=(
                    f"Net expected value ₹{ev.net_expected_value:.2f} is below the "
                    f"₹{self._policy.min_net_expected_value:.2f} floor -- not worth pursuing."
                ),
                meta=meta,
            )
        if shadow:
            return self._entry(
                txn,
                decision,
                diagnosis,
                executed=False,
                method=ExecutionMethod.SHADOW,
                projected=RecoveryOutcome.NOT_APPLICABLE,
                detail=f"Shadow mode: would {action.value} via {ev.channel.value}.",
                meta=meta,
            )

        idem = execution_key(txn.id, action, self._policy.version)
        if self._idem is not None and self._idem.seen(idem):
            return self._entry(
                txn,
                decision,
                diagnosis,
                executed=False,
                method=ExecutionMethod.BLOCKED,
                projected=RecoveryOutcome.NOT_APPLICABLE,
                detail="Already executed in a prior run (idempotency) -- earlier result stands.",
                meta=meta,
                idempotency_key=idem,
            )

        if action in RETRY_ACTIONS:
            entry = self._retry(txn, decision, diagnosis, action, rate, meta, idem)
        else:
            entry = self._message(txn, decision, diagnosis, action, rate, meta, idem)

        if self._idem is not None:
            self._idem.mark(idem)
        return entry

    # -- action handlers --------------------------------------------
    def _retry(
        self,
        txn: Transaction,
        decision: RecoveryDecision,
        diagnosis: Diagnosis,
        action: DiagnosisAction,
        rate: float,
        meta: _Meta,
        idem: str,
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
            projected=project_outcome(rate=rate, transaction_id=txn.id),
            detail=f"{kind} {link.id} ({link.short_url}) -- retry {when}.",
            payment_link_id=link.id,
            meta=meta,
            idempotency_key=idem,
        )

    def _message(
        self,
        txn: Transaction,
        decision: RecoveryDecision,
        diagnosis: Diagnosis,
        action: DiagnosisAction,
        rate: float,
        meta: _Meta,
        idem: str,
    ) -> AuditLogEntry:
        text, method = self._draft_message(txn, diagnosis, action, meta.channel)
        return self._entry(
            txn,
            decision,
            diagnosis,
            executed=True,
            method=method,
            projected=project_outcome(rate=rate, transaction_id=txn.id),
            detail=text,
            meta=meta,
            idempotency_key=idem,
        )

    def _draft_message(
        self, txn: Transaction, diagnosis: Diagnosis, action: DiagnosisAction, channel: Channel
    ) -> tuple[str, ExecutionMethod]:
        ask = (
            "update or switch their payment method"
            if action is DiagnosisAction.REQUEST_UPDATE
            else "complete the pending payment"
        )
        try:
            reply = self._llm.complete(
                _MESSAGE_PROMPT.format(
                    channel=channel.value,
                    cause=diagnosis.root_cause,
                    amount=txn.amount.format(),
                    ask=ask,
                    channel_hint=_CHANNEL_HINT.get(channel, ""),
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
        held_out: bool = False,
        meta: _Meta | None = None,
        idempotency_key: str | None = None,
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
            held_out=held_out,
            idempotency_key=idempotency_key,
            policy_version=meta.policy_version if meta else None,
            conversion_key=meta.conversion_key if meta else None,
            predicted_rate=meta.predicted_rate if meta else None,
            net_expected_value=meta.net_expected_value if meta else None,
            channel=meta.channel if meta else None,
            channel_cost=meta.channel_cost if meta else None,
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
