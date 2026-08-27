"""PaymentGatewayPort backed by Razorpay's payment-links API.

Razorpay's *test-mode* API rate-limits aggressively (a handful of link
creations per minute). Creating a real link for every retry in a
180-transaction batch would take many minutes and mostly 429. So this
adapter spends a bounded budget of genuinely-live creations -- enough to
prove the integration end-to-end -- and falls back to a clearly-labelled
simulated link for the rest. A throttled attempt is reported distinctly
(`RAZORPAY_API_RATELIMITED`) so the dashboard never overstates how much
was live.
"""

from __future__ import annotations

import time

from revenue_recovery.adapters.simulated_gateway import SimulatedGateway
from revenue_recovery.domain.enums import ExecutionMethod
from revenue_recovery.domain.money import Money
from revenue_recovery.logging import get_logger
from revenue_recovery.ports.payments import PaymentLink

log = get_logger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 2.0)


def _is_rate_limit(exc: Exception) -> bool:
    return "too many requests" in str(exc).lower() or "rate" in type(exc).__name__.lower()


class RazorpayGateway:
    live = True

    _CIRCUIT_TRIP_AFTER = 3  # consecutive rate-limits -> stop trying live this run

    def __init__(self, key_id: str, key_secret: str, *, live_link_budget: int = 8) -> None:
        self._auth = (key_id, key_secret)
        self._budget = live_link_budget
        self._consecutive_rate_limits = 0
        self._client = None
        self._sim = SimulatedGateway()

    @property
    def live_links_remaining(self) -> int:
        return self._budget

    @property
    def _circuit_open(self) -> bool:
        return self._consecutive_rate_limits >= self._CIRCUIT_TRIP_AFTER

    def _ensure_client(self) -> object:
        if self._client is None:
            import razorpay

            self._client = razorpay.Client(auth=self._auth)
        return self._client

    def create_payment_link(
        self, *, amount: Money, order_id: str, description: str, note: str
    ) -> PaymentLink:
        if self._budget <= 0 or self._circuit_open:
            return self._sim.create_payment_link(
                amount=amount, order_id=order_id, description=description, note=note
            )

        # Spend one budget unit per real attempt, win or lose, so the budget
        # is a hard bound on how long the live path can run.
        self._budget -= 1
        client = self._ensure_client()
        payload = {
            "amount": amount.paise,
            "currency": "INR",
            "description": description[:2048],
            "notify": {"sms": False, "email": False},
            "reminder_enable": True,
            "notes": {"original_order_id": order_id, "recovery_reason": note[:250]},
        }

        for attempt in range(_MAX_ATTEMPTS):
            try:
                raw = client.payment_link.create(payload)  # type: ignore[attr-defined]
                self._consecutive_rate_limits = 0
                log.info("razorpay_link_created", link_id=raw["id"], order_id=order_id)
                return PaymentLink(
                    id=raw["id"],
                    short_url=raw["short_url"],
                    amount=amount,
                    method=ExecutionMethod.RAZORPAY_API,
                )
            except Exception as exc:  # noqa: BLE001
                if _is_rate_limit(exc) and attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                if _is_rate_limit(exc):
                    self._consecutive_rate_limits += 1
                method = (
                    ExecutionMethod.RAZORPAY_API_RATELIMITED
                    if _is_rate_limit(exc)
                    else ExecutionMethod.RAZORPAY_API_SIMULATED
                )
                log.warning("razorpay_link_degraded", reason=str(exc)[:120], fell_back_to=method)
                fake = self._sim.create_payment_link(
                    amount=amount, order_id=order_id, description=description, note=note
                )
                return PaymentLink(
                    id=fake.id, short_url=fake.short_url, amount=amount, method=method
                )

        raise AssertionError("unreachable")
