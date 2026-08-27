import pytest

from revenue_recovery.domain.money import Money


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0, "₹0"),
        (999, "₹999"),
        (1000, "₹1,000"),
        (101394, "₹1,01,394"),
        (12345678, "₹1,23,45,678"),
    ],
)
def test_indian_digit_grouping(amount: int, expected: str) -> None:
    assert Money(amount).format() == expected


def test_paise_roundtrip() -> None:
    assert Money("199.99").paise == 19999
    assert Money.from_paise(19999).rupees == Money("199.99").rupees


def test_arithmetic_and_ratio() -> None:
    assert (Money(100) + Money(50)) == Money(150)
    assert (Money(100) - Money(150)) == Money(-50)
    assert Money(25).ratio(Money(100)) == 0.25
    assert Money(1).ratio(Money.zero()) == 0.0


def test_invalid_amount_raises_valueerror_naming_the_value() -> None:
    with pytest.raises(ValueError, match="not-a-number"):
        Money("not-a-number")


def test_sum_starts_from_zero() -> None:
    total = sum((Money(x) for x in (10, 20, 30)), Money.zero())
    assert total == Money(60)
