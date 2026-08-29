"""PaymentGatewayPort backed by Razorpay.

The recovery mechanism is: give the customer a fresh place to pay. The
ideal primitive is a **Payment Link** (a hosted checkout page + its own
short URL). Razorpay's *test mode* caps payment-link creation at 30 per
account, ever, and rate-limits the endpoint hard -- so this adapter:

  1. spends a bounded budget of genuinely-live creations (enough to prove
     the integration), backing off on 429;
  2. when payment links are capped, falls back to creating a live
     **Order** instead (no 30-cap) -- still a real Razorpay object the
     merchant can settle via Checkout, reported as `RAZORPAY_ORDER`;
  3. only if both fail does it return a clearly-labelled simulated link.

Every path is labelled so the dashboard never overstates how much was
live.
"""

from __future__ import annotations

import threading
import time

from recover_ai.adapters.simulated_gateway import SimulatedGateway
from recover_ai.domain.enums import ExecutionMethod
from recover_ai.domain.money import Money
from recover_ai.logging import get_logger
from recover_ai.ports.payments import PaymentLink

log = get_logger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0)
_DASHBOARD_ORDER = "https://dashboard.razorpay.com/app/orders/"


def _is_rate_limit(exc: Exception) -> bool:
    return "too many requests" in str(exc).lower() or "rate" in type(exc).__name__.lower()


def _is_payment_link_capped(exc: Exception) -> bool:
    # test accounts cap payment_link creation at 30, ever -- never recovers
    m = str(exc).lower()
    return "limit" in m and "reached" in m


class RazorpayGateway:
    live = True

    _CIRCUIT_TRIP_AFTER = 3  # consecutive rate-limits -> stop trying live this run

    def __init__(self, key_id: str, key_secret: str, *, live_link_budget: int = 8) -> None:
        self._auth = (key_id, key_secret)
        self._budget = live_link_budget
        self._consecutive_rate_limits = 0
        self._payment_links_capped = False
        self._client = None
        self._sim = SimulatedGateway()
        self._lock = threading.Lock()  # guards the mutable counters above

    @property
    def live_links_remaining(self) -> int:
        return self._budget

    @property
    def _circuit_open(self) -> bool:
        return self._consecutive_rate_limits >= self._CIRCUIT_TRIP_AFTER

    def _ensure_client(self) -> object:
        with self._lock:
            if self._client is None:
                import razorpay

                self._client = razorpay.Client(auth=self._auth)
            return self._client

    # -- public --------------------------------------------------------
    def create_payment_link(
        self, *, amount: Money, order_id: str, description: str, note: str
    ) -> PaymentLink:
        with self._lock:
            if self._budget <= 0 or self._circuit_open:
                spend = False
            else:
                # one budget unit per real attempt, win or lose
                self._budget -= 1
                spend = True

        if spend:
            client = self._ensure_client()
            if not self._payment_links_capped:
                got = self._try_payment_link(client, amount, order_id, description, note)
                if got is not None:
                    return got
            # payment links unavailable -> a live Order still proves the integration
            got = self._try_order(client, amount, order_id, note)
            if got is not None:
                return got

        method = (
            ExecutionMethod.RAZORPAY_API_RATELIMITED
            if self._consecutive_rate_limits and not self._payment_links_capped
            else ExecutionMethod.RAZORPAY_API_SIMULATED
        )
        log.warning("razorpay_link_degraded", fell_back_to=method)
        fake = self._sim.create_payment_link(
            amount=amount, order_id=order_id, description=description, note=note
        )
        return PaymentLink(id=fake.id, short_url=fake.short_url, amount=amount, method=method)

    # -- primitives -------------------------------------------------
    def _try_payment_link(
        self, client: object, amount: Money, order_id: str, description: str, note: str
    ) -> PaymentLink | None:
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
                with self._lock:
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
                with self._lock:
                    if _is_rate_limit(exc):
                        self._consecutive_rate_limits += 1
                    if _is_payment_link_capped(exc):
                        self._payment_links_capped = True
                log.warning("razorpay_link_unavailable", reason=str(exc)[:120])
                return None
        return None

    def _try_order(
        self, client: object, amount: Money, order_id: str, note: str
    ) -> PaymentLink | None:
        try:
            raw = client.order.create(  # type: ignore[attr-defined]
                {
                    "amount": amount.paise,
                    "currency": "INR",
                    "receipt": f"recover_{order_id}"[:40],
                    "notes": {"original_order_id": order_id, "recovery_reason": note[:250]},
                }
            )
            with self._lock:
                self._consecutive_rate_limits = 0
            log.info("razorpay_order_created", order=raw["id"], original=order_id)
            return PaymentLink(
                id=raw["id"],
                short_url=f"{_DASHBOARD_ORDER}{raw['id']}",
                amount=amount,
                method=ExecutionMethod.RAZORPAY_ORDER,
            )
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                if _is_rate_limit(exc):
                    self._consecutive_rate_limits += 1
            log.warning("razorpay_order_failed", reason=str(exc)[:120])
            return None
