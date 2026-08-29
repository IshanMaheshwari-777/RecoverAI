"""Diagnosis layer: what went wrong, and what the first move should be.

Design principle -- deterministic by default, AI only where it earns its
place. Seven of the eight failure reasons have exactly one sane response
regardless of context, so a lookup table decides them: an LLM call would
add latency, cost, and a hallucination surface for zero judgement
benefit. The routing to the LLM is *confidence-weighted*: a reason is
sent to the model when it is in the ambiguous set (a bare bank decline,
where the right move genuinely depends on attempt history and amount) or
when the matched rule's own confidence is below a floor. The model
returns a recommendation with reasoning; it never decides retries or
stops itself -- the recovery layer enforces those.
"""

from __future__ import annotations

import json

from revenue_recovery.domain.diagnosis import Diagnosis
from revenue_recovery.domain.enums import (
    DiagnosisAction,
    DiagnosisMethod,
    FailureReason,
    TransactionStatus,
)
from revenue_recovery.domain.errors import LLMUnavailableError, NothingToDiagnoseError
from revenue_recovery.domain.models import Transaction
from revenue_recovery.logging import get_logger
from revenue_recovery.ports.llm import LLMPort

log = get_logger(__name__)

_LLM_CONFIDENCE_FLOOR = 0.7
_AMBIGUOUS: frozenset[FailureReason] = frozenset({FailureReason.PAYMENT_DECLINED})

# reason -> (action, one-sentence cause, confidence)
_RULES: dict[FailureReason, tuple[DiagnosisAction, str, float]] = {
    FailureReason.INVALID_OTP: (
        DiagnosisAction.RETRY_NOW,
        "The customer mistyped the OTP -- prompt them to retry with a fresh one.",
        0.95,
    ),
    FailureReason.INSUFFICIENT_FUNDS: (
        DiagnosisAction.RETRY_LATER,
        "The account was short at the time -- wait, then retry; offer an alternate method.",
        0.9,
    ),
    FailureReason.GATEWAY_TIMEOUT: (
        DiagnosisAction.RETRY_NOW,
        "A transient gateway timeout, not a customer or bank problem -- safe to auto-retry.",
        0.95,
    ),
    FailureReason.NETWORK_ISSUE: (
        DiagnosisAction.RETRY_NOW,
        "A transient network failure mid-processing -- safe to auto-retry immediately.",
        0.95,
    ),
    FailureReason.CARD_EXPIRED: (
        DiagnosisAction.REQUEST_UPDATE,
        "The card has expired -- no retry can succeed until the customer updates it.",
        0.97,
    ),
    FailureReason.PAYMENT_CANCELLED: (
        DiagnosisAction.SEND_REMINDER,
        "The customer backed out at checkout -- a gentle nudge, not a retry.",
        0.9,
    ),
    FailureReason.RISK_CHECK_FAILED: (
        DiagnosisAction.DO_NOT_CONTACT,
        "Blocked by fraud / risk checks -- a compliance stop. Never retry or contact.",
        0.99,
    ),
}

_LLM_PROMPT = """\
A payment failed with a generic bank decline (no specific reason code attached).

Transaction context:
- attempt number so far: {attempt}
- amount: {amount}
- payment method: {method}

Choose the single best next action from exactly these options:
retry_now, retry_later, request_update, send_reminder, do_not_contact.

Guidance: a first generic decline is usually safe to retry shortly. Three or
more declines on the same order point at the instrument itself -- ask the
customer to use a different method rather than retrying again. Large amounts
warrant more caution than small ones.

Respond with ONLY minified JSON, no prose:
{{"action": "...", "root_cause": "<one sentence>", "confidence": 0.0}}
"""


class DiagnosisEngine:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def diagnose(self, txn: Transaction) -> Diagnosis:
        if txn.status is TransactionStatus.CAPTURED:
            raise NothingToDiagnoseError(f"{txn.id} is captured")

        if txn.status is TransactionStatus.ABANDONED:
            return Diagnosis(
                transaction_id=txn.id,
                root_cause="Checkout opened but no payment attempt was made.",
                action=DiagnosisAction.SEND_REMINDER,
                method=DiagnosisMethod.RULE,
                confidence=0.9,
                reasoning="Abandonment has no error object -- nothing for a model to reason about.",
            )

        reason = txn.reason or FailureReason.UNKNOWN
        rule = _RULES.get(reason)

        route_to_llm = (
            reason in _AMBIGUOUS
            or (rule is not None and rule[2] < _LLM_CONFIDENCE_FLOOR)
            or (rule is None and txn.error is not None)
        )

        if rule is not None and not route_to_llm:
            action, cause, confidence = rule
            return Diagnosis(
                transaction_id=txn.id,
                root_cause=cause,
                action=action,
                method=DiagnosisMethod.RULE,
                confidence=confidence,
            )

        if route_to_llm:
            return self._llm_diagnose(txn, rule)

        # Neither a rule nor an LLM route: an unrecognised reason with no error
        # object. Do nothing rather than guess.
        return Diagnosis(
            transaction_id=txn.id,
            root_cause=f"Unrecognised failure reason: {reason.value}.",
            action=DiagnosisAction.DO_NOT_CONTACT,
            method=DiagnosisMethod.UNHANDLED,
            confidence=0.0,
            reasoning="No rule and no LLM route cover this -- defaulting to no action.",
        )

    def _llm_diagnose(
        self, txn: Transaction, rule: tuple[DiagnosisAction, str, float] | None
    ) -> Diagnosis:
        prompt = _LLM_PROMPT.format(
            attempt=txn.attempt_number,
            amount=txn.amount.format(),
            method=txn.method.value,
        )
        try:
            reply = self._llm.complete(prompt, max_tokens=400)
            payload = _parse_json(reply.text)
            action = DiagnosisAction(str(payload["action"]))
            return Diagnosis(
                transaction_id=txn.id,
                root_cause=str(payload.get("root_cause", "Generic bank decline."))[:280],
                action=action,
                method=DiagnosisMethod.LLM,
                confidence=float(payload.get("confidence", 0.6)),  # type: ignore[arg-type]
                reasoning="Routed to the LLM: the right move for a bare decline depends on "
                "attempt history and amount, not the error code.",
                model_name=reply.model,
                latency_ms=reply.latency_ms,
            )
        except (LLMUnavailableError, KeyError, ValueError, json.JSONDecodeError) as exc:
            log.debug("diagnosis_llm_fallback", txn=txn.id, error=str(exc)[:120])
            return self._fallback(txn, rule)

    @staticmethod
    def _fallback(txn: Transaction, rule: tuple[DiagnosisAction, str, float] | None) -> Diagnosis:
        if rule is not None:
            action, cause, _ = rule
        elif txn.attempt_number >= 3:
            action, cause = (
                DiagnosisAction.REQUEST_UPDATE,
                ("Repeated generic declines -- ask the customer to switch payment method."),
            )
        else:
            action, cause = (
                DiagnosisAction.RETRY_LATER,
                ("Generic bank decline -- conservative fallback: wait, then retry once."),
            )
        return Diagnosis(
            transaction_id=txn.id,
            root_cause=cause,
            action=action,
            method=DiagnosisMethod.LLM_FALLBACK,
            confidence=0.4,
            reasoning="LLM diagnosis unavailable -- used the conservative fallback rule.",
        )


def _parse_json(text: str) -> dict[str, object]:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed: dict[str, object] = json.loads(cleaned)
    return parsed
