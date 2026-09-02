"""Closed vocabularies shared by every layer.

These mirror the shapes Razorpay's API actually returns (`status`,
`method`, and the `error.source` / `error.reason` fields on a failed
payment). Keeping them as `StrEnum` means they serialise to plain strings
in JSON while still being type-checked in Python.
"""

from __future__ import annotations

from enum import StrEnum


class TransactionStatus(StrEnum):
    CAPTURED = "captured"  # payment succeeded
    FAILED = "failed"  # an attempt was made and the gateway rejected it
    ABANDONED = "abandoned"  # checkout opened, no attempt made


class PaymentMethod(StrEnum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"


class ErrorSource(StrEnum):
    CUSTOMER = "customer"
    BANK = "bank"
    GATEWAY = "gateway"
    BUSINESS = "business"
    NETWORK = "network"


class FailureReason(StrEnum):
    """The `error.reason` values we know how to act on, plus a catch-all."""

    INVALID_OTP = "invalid_otp"
    PAYMENT_DECLINED = "payment_declined"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    GATEWAY_TIMEOUT = "gateway_timeout"
    PAYMENT_CANCELLED = "payment_cancelled"
    CARD_EXPIRED = "card_expired"
    NETWORK_ISSUE = "network_issue"
    RISK_CHECK_FAILED = "risk_check_failed"
    UNKNOWN = "unknown"


class DiagnosisAction(StrEnum):
    """What the diagnosis layer thinks the first move should be."""

    RETRY_NOW = "retry_now"
    RETRY_LATER = "retry_later"
    REQUEST_UPDATE = "request_update"
    SEND_REMINDER = "send_reminder"
    DO_NOT_CONTACT = "do_not_contact"


class DiagnosisMethod(StrEnum):
    """How a diagnosis was reached -- the rule/LLM split, made auditable."""

    RULE = "rule"
    LLM = "llm"
    LLM_FALLBACK = "llm_fallback"
    UNHANDLED = "unhandled"


class ExecutionMethod(StrEnum):
    RAZORPAY_API = "razorpay_api"  # live payment link
    RAZORPAY_ORDER = "razorpay_order"  # live order (payment-link cap hit)
    RAZORPAY_API_SIMULATED = "razorpay_api_simulated"
    RAZORPAY_API_RATELIMITED = "razorpay_api_ratelimited"
    LLM_MESSAGE = "llm_message"
    TEMPLATE_MESSAGE = "template_message"
    BLOCKED = "blocked"
    UNHANDLED = "unhandled"
    PIPELINE_ERROR = "pipeline_error"
    HOLDOUT_CONTROL = "holdout_control"  # in the causal control group -- decided, not executed
    RETRY_HELD_INCIDENT = "retry_held_incident"  # rail is degraded -- retry deferred
    SKIPPED_NEGATIVE_EV = "skipped_negative_ev"  # not worth the cost of pursuing
    SHADOW = "shadow"  # shadow mode -- what we would have done


class Channel(StrEnum):
    """How a customer is reached. Payment link is its own channel; the
    rest are messaging rails, cheapest-effective first."""

    PAYMENT_LINK = "payment_link"
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


MESSAGING_LADDER: tuple[Channel, ...] = (
    Channel.IN_APP,
    Channel.EMAIL,
    Channel.SMS,
    Channel.WHATSAPP,
)


class RecoveryOutcome(StrEnum):
    RECOVERED = "recovered"  # projected or confirmed conversion
    NOT_RECOVERED = "not_recovered"
    PENDING = "pending"  # action taken, awaiting a real webhook
    NOT_APPLICABLE = "n/a"  # nothing was executed (blocked / error)


CONTACT_ACTIONS: frozenset[DiagnosisAction] = frozenset(
    {DiagnosisAction.SEND_REMINDER, DiagnosisAction.REQUEST_UPDATE}
)
RETRY_ACTIONS: frozenset[DiagnosisAction] = frozenset(
    {DiagnosisAction.RETRY_NOW, DiagnosisAction.RETRY_LATER}
)
