"""Shared fixtures and test doubles.

Every test runs with credentials stripped and the live-link budget at
zero, so a developer with a real `.env` gets the same results as CI with
none. Tests that genuinely need a real API are marked `integration` and
skipped by default.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from recover_ai.config import Settings, get_settings
from recover_ai.domain.enums import (
    ErrorSource,
    FailureReason,
    PaymentMethod,
    TransactionStatus,
)
from recover_ai.domain.errors import LLMUnavailableError
from recover_ai.domain.models import ErrorDetail, Transaction
from recover_ai.domain.money import Money
from recover_ai.ports.llm import LLMReply


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Strip credentials and isolate filesystem state.

    We `chdir` into a tmp dir so pydantic-settings can't find the repo's
    `.env`, and pipeline reports write under the tmp dir, not `data/`.
    """
    for var in (
        "RAZORPAY_KEY_ID",
        "RAZORPAY_KEY_SECRET",
        "ANTHROPIC_API_KEY",
        "RAZORPAY_LIVE_LINK_BUDGET",
        "RECOVERY_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


class FakeLLM:
    """A scriptable LLMPort. `available` and the reply text are set per test."""

    def __init__(self, *, available: bool = True, text: str = "", raises: bool = False) -> None:
        self._available = available
        self._text = text
        self._raises = raises
        self.calls: list[str] = []

    @property
    def available(self) -> bool:
        return self._available

    @property
    def model(self) -> str:
        return "fake-model"

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> LLMReply:
        self.calls.append(prompt)
        if self._raises or not self._available:
            raise LLMUnavailableError("fake failure")
        return LLMReply(text=self._text, model="fake-model", latency_ms=7)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM(available=False)


def make_txn(
    *,
    id: str = "pay_test",
    customer_id: str = "cust_test",
    amount: float = 1000.0,
    method: PaymentMethod = PaymentMethod.CARD,
    status: TransactionStatus = TransactionStatus.FAILED,
    reason: FailureReason | None = FailureReason.NETWORK_ISSUE,
    attempt_number: int = 1,
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> Transaction:
    error = None
    if reason is not None:
        error = ErrorDetail(
            code="X",
            description="x",
            source=ErrorSource.BANK,
            step="payment_authorization",
            reason=reason,
        )
    return Transaction(
        id=id,
        order_id=f"order_{id}",
        customer_id=customer_id,
        amount=Money(amount),
        method=method,
        status=status,
        created_at=datetime.fromisoformat(created_at),
        attempt_number=attempt_number,
        error=error,
    )


@pytest.fixture
def txn_factory():
    return make_txn
