"""RazorpayGateway degradation logic — budget, backoff, circuit, and the
payment-link -> order -> simulated fallback chain.

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


class _Endpoint:
    def __init__(self, *, fail_with: Exception | None = None, id_prefix: str = "x") -> None:
        self._fail_with = fail_with
        self._prefix = id_prefix
        self.calls = 0

    def create(self, _payload: dict) -> dict:
        self.calls += 1
        if self._fail_with is not None:
            raise self._fail_with
        return {"id": f"{self._prefix}_{self.calls}", "short_url": "https://rzp.io/i/x"}


class _FakeClient:
    def __init__(self, payment_link: _Endpoint, order: _Endpoint) -> None:
        self.payment_link = payment_link
        self.order = order


def _gateway(
    *,
    link: _Endpoint | None = None,
    order: _Endpoint | None = None,
    budget: int = 8,
) -> tuple[RazorpayGateway, _FakeClient]:
    link = link or _Endpoint(id_prefix="plink")
    order = order or _Endpoint(id_prefix="order")
    gw = RazorpayGateway("k", "s", live_link_budget=budget)
    client = _FakeClient(link, order)
    gw._client = client  # skip the lazy razorpay import
    return gw, client


def _make(gw: RazorpayGateway) -> ExecutionMethod:
    return gw.create_payment_link(
        amount=Money(1000), order_id="order_1", description="d", note="n"
    ).method


def test_successful_payment_link_is_marked_live() -> None:
    gw, _ = _gateway()
    assert _make(gw) is ExecutionMethod.RAZORPAY_API


def test_budget_is_a_hard_cap_on_live_attempts() -> None:
    gw, client = _gateway(budget=2)
    methods = [_make(gw) for _ in range(5)]
    assert methods[:2] == [ExecutionMethod.RAZORPAY_API] * 2
    assert all(m is ExecutionMethod.RAZORPAY_API_SIMULATED for m in methods[2:])
    assert client.payment_link.calls == 2 and client.order.calls == 0


def test_payment_link_cap_falls_back_to_a_live_order() -> None:
    link = _Endpoint(fail_with=Exception("test mode limit of 30 reached for payment_link"))
    gw, client = _gateway(link=link)
    assert _make(gw) is ExecutionMethod.RAZORPAY_ORDER
    assert client.payment_link.calls == 1  # not a rate limit -> no retry
    # subsequent calls skip the capped endpoint entirely
    assert _make(gw) is ExecutionMethod.RAZORPAY_ORDER
    assert client.payment_link.calls == 1
    assert client.order.calls == 2


def test_rate_limit_retries_then_degrades_as_ratelimited() -> None:
    link = _Endpoint(fail_with=Exception("Too many requests"))
    order = _Endpoint(fail_with=Exception("Too many requests"))
    gw, client = _gateway(link=link, order=order)
    assert _make(gw) is ExecutionMethod.RAZORPAY_API_RATELIMITED
    assert client.payment_link.calls == 3  # _MAX_ATTEMPTS


def test_both_endpoints_down_degrades_to_simulated() -> None:
    link = _Endpoint(fail_with=Exception("bad request"))
    order = _Endpoint(fail_with=Exception("bad request"))
    gw, _ = _gateway(link=link, order=order)
    assert _make(gw) is ExecutionMethod.RAZORPAY_API_SIMULATED


@pytest.mark.parametrize("budget", [0, -1])
def test_zero_budget_never_touches_the_api(budget: int) -> None:
    gw, client = _gateway(budget=budget)
    assert _make(gw) is ExecutionMethod.RAZORPAY_API_SIMULATED
    assert client.payment_link.calls == 0 and client.order.calls == 0
