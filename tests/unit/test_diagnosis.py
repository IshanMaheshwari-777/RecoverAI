import pytest

from revenue_recovery.domain.enums import (
    DiagnosisAction,
    DiagnosisMethod,
    FailureReason,
    TransactionStatus,
)
from revenue_recovery.domain.errors import NothingToDiagnoseError
from revenue_recovery.services.diagnosis import _RULES, DiagnosisEngine
from tests.conftest import FakeLLM


@pytest.mark.parametrize("reason", list(_RULES))
def test_every_rule_reason_resolves_by_rule(reason: FailureReason, txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    d = engine.diagnose(txn_factory(reason=reason))
    assert d.method is DiagnosisMethod.RULE


def test_risk_check_is_do_not_contact(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    d = engine.diagnose(txn_factory(reason=FailureReason.RISK_CHECK_FAILED))
    assert d.action is DiagnosisAction.DO_NOT_CONTACT


def test_card_expired_requests_update(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    d = engine.diagnose(txn_factory(reason=FailureReason.CARD_EXPIRED))
    assert d.action is DiagnosisAction.REQUEST_UPDATE


def test_abandoned_gets_reminder_via_rule(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    d = engine.diagnose(txn_factory(status=TransactionStatus.ABANDONED, reason=None))
    assert d.method is DiagnosisMethod.RULE
    assert d.action is DiagnosisAction.SEND_REMINDER


def test_ambiguous_decline_routes_to_llm_when_available(txn_factory) -> None:
    llm = FakeLLM(
        available=True, text='{"action":"retry_now","root_cause":"first decline","confidence":0.8}'
    )
    engine = DiagnosisEngine(llm)
    d = engine.diagnose(txn_factory(reason=FailureReason.PAYMENT_DECLINED))
    assert d.method is DiagnosisMethod.LLM
    assert d.action is DiagnosisAction.RETRY_NOW
    assert d.latency_ms == 7
    assert llm.calls, "the LLM should have been consulted"


def test_ambiguous_decline_falls_back_when_llm_unavailable(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    d = engine.diagnose(txn_factory(reason=FailureReason.PAYMENT_DECLINED, attempt_number=1))
    assert d.method is DiagnosisMethod.LLM_FALLBACK
    assert d.action is DiagnosisAction.RETRY_LATER


def test_ambiguous_decline_fallback_escalates_after_repeated_attempts(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    d = engine.diagnose(txn_factory(reason=FailureReason.PAYMENT_DECLINED, attempt_number=3))
    assert d.action is DiagnosisAction.REQUEST_UPDATE


def test_llm_garbage_response_falls_back(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=True, text="not json at all"))
    d = engine.diagnose(txn_factory(reason=FailureReason.PAYMENT_DECLINED))
    assert d.method is DiagnosisMethod.LLM_FALLBACK


def test_unknown_reason_defaults_to_do_not_contact(txn_factory) -> None:
    engine = DiagnosisEngine(
        FakeLLM(available=True, text='{"action":"retry_now","root_cause":"x","confidence":0.5}')
    )
    txn = txn_factory(reason=None)
    # an error object with an unrecognised reason -> routed to LLM;
    # here there's no error at all -> unhandled
    d = engine.diagnose(txn)
    assert d.method is DiagnosisMethod.UNHANDLED
    assert d.action is DiagnosisAction.DO_NOT_CONTACT


def test_captured_transaction_raises(txn_factory) -> None:
    engine = DiagnosisEngine(FakeLLM(available=False))
    with pytest.raises(NothingToDiagnoseError):
        engine.diagnose(txn_factory(status=TransactionStatus.CAPTURED, reason=None))
