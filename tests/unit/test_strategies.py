from datetime import timedelta

from recover_ai.domain.enums import FailureReason, PaymentMethod
from recover_ai.services.strategies import retry_delay, strategy_for


def test_upi_retries_sooner_than_netbanking() -> None:
    upi = retry_delay(PaymentMethod.UPI, FailureReason.GATEWAY_TIMEOUT, 1)
    nb = retry_delay(PaymentMethod.NETBANKING, FailureReason.GATEWAY_TIMEOUT, 1)
    assert upi < nb


def test_insufficient_funds_overrides_method_floor() -> None:
    d = retry_delay(PaymentMethod.UPI, FailureReason.INSUFFICIENT_FUNDS, 1)
    assert d >= timedelta(hours=24)


def test_delay_backs_off_with_attempts_and_is_capped() -> None:
    d1 = retry_delay(PaymentMethod.CARD, FailureReason.PAYMENT_DECLINED, 1)
    d3 = retry_delay(PaymentMethod.CARD, FailureReason.PAYMENT_DECLINED, 3)
    assert d3 > d1
    assert d3 <= timedelta(hours=48)


def test_each_method_has_a_strategy_with_a_distinct_alternate() -> None:
    for m in PaymentMethod:
        s = strategy_for(m)
        assert s.alternate_method is not m
        assert s.max_retries >= 2
