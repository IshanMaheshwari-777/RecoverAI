"""RazorpayGateway degradation logic — budget, backoff, circuit, quota.

The real razorpay client is swapped for a fake so no network is touched.
"""

from __future__ import annotations

import pytest

from revenue_recovery.adapters import razorpay_gateway
from revenue_recovery.adapters.razorpay_gateway import RazorpayGateway
from revenue_recovery.domain.enums import ExecutionMethod
from revenue_recovery.domain.money import Money


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(razorpay_gateway.time, "sleep", lambda _s: None)


class _FakePaymentLink:
    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self._fail_with = fail_with
        self.calls = 0

    def create(self, _payload: dict) -> dict:
        self.calls += 1
        if self._fail_with is not None:
            raise self._fail_with
        return {"id": f"plink_LIVE{self.calls}", "short_url": "https://rzp.io/i/live"}


class _FakeClient:
    def __init__(self, link: _FakePaymentLink) -> None:
        self.payment_link = link


def _gateway(link: _FakePaymentLink, *, budget: int = 8) -> RazorpayGateway:
    gw = RazorpayGateway("k", "s", live_link_budget=budget)
    gw._client = _FakeClient(link)  # skip the lazy razorpay import
    return gw


def _make(gw: RazorpayGateway) -> ExecutionMethod:
    return gw.create_payment_link(
        amount=Money(1000), order_id="order_1", description="d", note="n"
    ).method


def test_successful_creation_is_marked_live() -> None:
    gw = _gateway(_FakePaymentLink())
    assert _make(gw) is ExecutionMethod.RAZORPAY_API


def test_budget_is_a_hard_cap_on_live_attempts() -> None:
    link = _FakePaymentLink()
    gw = _gateway(link, budget=2)
    methods = [_make(gw) for _ in range(5)]
    assert methods[:2] == [ExecutionMethod.RAZORPAY_API] * 2
    assert all(m is ExecutionMethod.RAZORPAY_API_SIMULATED for m in methods[2:])
    assert link.calls == 2  # never called the API past the budget


def test_rate_limit_retries_then_degrades_and_trips_the_circuit() -> None:
    link = _FakePaymentLink(fail_with=Exception("Too many requests"))
    gw = _gateway(link, budget=8)
    # first few attempts retry (3x each) then fall back as rate-limited
    first = _make(gw)
    assert first is ExecutionMethod.RAZORPAY_API_RATELIMITED
    assert link.calls == 3  # _MAX_ATTEMPTS
    # after 3 consecutive rate-limits the circuit opens -> no more API calls
    for _ in range(4):
        _make(gw)
    assert link.calls <= 9  # 3 attempts x 3 tries, then circuit-open short-circuits


def test_quota_exhausted_stops_live_immediately_and_forever() -> None:
    link = _FakePaymentLink(fail_with=Exception("test mode limit of 30 reached for payment_link"))
    gw = _gateway(link, budget=8)
    assert _make(gw) is ExecutionMethod.RAZORPAY_API_SIMULATED
    assert link.calls == 1  # not a rate limit -> no retry
    _make(gw)
    assert link.calls == 1  # circuit permanently open, API never touched again


@pytest.mark.parametrize("budget", [0, -1])
def test_zero_budget_never_touches_the_api(budget: int) -> None:
    link = _FakePaymentLink()
    gw = _gateway(link, budget=budget)
    assert _make(gw) is ExecutionMethod.RAZORPAY_API_SIMULATED
    assert link.calls == 0
