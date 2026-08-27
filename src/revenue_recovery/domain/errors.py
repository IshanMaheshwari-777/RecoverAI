"""Domain-level exceptions.

Adapters translate vendor-specific failures (razorpay.errors.*,
anthropic.APIError, ...) into these so the services never import a vendor
SDK's exception types.
"""

from __future__ import annotations


class RevenueRecoveryError(Exception):
    """Base class for every error this package raises deliberately."""


class NothingToDiagnoseError(RevenueRecoveryError):
    """Raised when a captured (successful) transaction reaches the diagnoser."""


class PaymentGatewayError(RevenueRecoveryError):
    """A payment-gateway call failed for a non-recoverable reason."""


class PaymentGatewayRateLimitedError(PaymentGatewayError):
    """The gateway throttled us; the caller may retry with backoff."""


class LLMUnavailableError(RevenueRecoveryError):
    """No usable LLM credential, or the LLM call failed. Callers fall back."""
