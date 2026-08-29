"""A tiny money type.

Payments are integer paise on the wire and rupees in the UI, and India
groups digits differently from the West (₹12,34,567, not ₹1,234,567).
Centralising that here keeps every layer honest about precision and
formatting.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering
from typing import Any

_TWO_PLACES = Decimal("0.01")


@total_ordering
class Money:
    """An amount in Indian rupees, stored as an exact Decimal."""

    __slots__ = ("_amount",)

    def __init__(self, amount: Decimal | int | float | str) -> None:
        try:
            self._amount = Decimal(str(amount)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValueError(f"not a valid monetary amount: {amount!r}") from exc

    # -- constructors -------------------------------------------------------
    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_paise(cls, paise: int) -> Money:
        return cls(Decimal(paise) / 100)

    # -- accessors --------------------------------------------------------
    @property
    def rupees(self) -> Decimal:
        return self._amount

    @property
    def paise(self) -> int:
        return int((self._amount * 100).to_integral_value(rounding=ROUND_HALF_UP))

    # -- arithmetic ------------------------------------------------------
    def __add__(self, other: Money) -> Money:
        return Money(self._amount + other._amount)

    def __sub__(self, other: Money) -> Money:
        return Money(self._amount - other._amount)

    def __mul__(self, factor: Decimal | int | float) -> Money:
        return Money(self._amount * Decimal(str(factor)))

    def ratio(self, other: Money) -> float:
        if other._amount == 0:
            return 0.0
        return float(self._amount / other._amount)

    # -- comparison / hashing ------------------------------------------
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Money) and other._amount == self._amount

    def __lt__(self, other: Money) -> bool:
        return self._amount < other._amount

    def __hash__(self) -> int:
        return hash(self._amount)

    # -- rendering ------------------------------------------------------
    def format(self, *, symbol: str = "₹", decimals: bool = False) -> str:
        quant = self._amount if decimals else self._amount.to_integral_value(ROUND_HALF_UP)
        sign = "-" if quant < 0 else ""
        digits = f"{abs(quant):.2f}" if decimals else f"{abs(quant):.0f}"
        whole, _, frac = digits.partition(".")
        grouped = _group_indian(whole)
        return f"{sign}{symbol}{grouped}" + (f".{frac}" if decimals else "")

    def __str__(self) -> str:
        return self.format()

    def __repr__(self) -> str:
        return f"Money({self._amount})"

    # -- pydantic integration ----------------------------------------
    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda m: float(m.rupees)
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> Money:
        if isinstance(value, Money):
            return value
        return cls(value)


def _group_indian(digits: str) -> str:
    """1234567 -> '12,34,567' (last group of 3, then groups of 2)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    parts.insert(0, head)
    return ",".join(parts) + "," + tail
