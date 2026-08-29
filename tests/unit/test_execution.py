from recover_ai.adapters.simulated_gateway import SimulatedGateway
from recover_ai.domain.diagnosis import Diagnosis
from recover_ai.domain.enums import (
    DiagnosisAction,
    DiagnosisMethod,
    ExecutionMethod,
    RecoveryOutcome,
)
from recover_ai.domain.recovery import RecoveryDecision
from recover_ai.services.execution import Executor
from recover_ai.services.outcomes import project_outcome
from tests.conftest import FakeLLM


def _diag(txn_id: str) -> Diagnosis:
    return Diagnosis(
        transaction_id=txn_id,
        root_cause="network blip",
        action=DiagnosisAction.RETRY_NOW,
        method=DiagnosisMethod.RULE,
        confidence=0.9,
    )


def _decision(txn, action: DiagnosisAction | None, *, blocked: bool = False) -> RecoveryDecision:
    return RecoveryDecision(
        transaction_id=txn.id,
        customer_id=txn.customer_id,
        diagnosis_action=DiagnosisAction.RETRY_NOW,
        final_action=action,
        blocked=blocked,
        reason="test",
    )


def test_blocked_decision_produces_an_entry_but_executes_nothing(txn_factory) -> None:
    txn = txn_factory()
    ex = Executor(SimulatedGateway(), FakeLLM(available=False))
    entry = ex.execute(txn, _decision(txn, None, blocked=True), _diag(txn.id))
    assert not entry.executed
    assert entry.execution_method is ExecutionMethod.BLOCKED
    assert entry.projected_outcome is RecoveryOutcome.NOT_APPLICABLE


def test_retry_creates_a_simulated_link_without_keys(txn_factory) -> None:
    txn = txn_factory()
    ex = Executor(SimulatedGateway(), FakeLLM(available=False))
    entry = ex.execute(txn, _decision(txn, DiagnosisAction.RETRY_NOW), _diag(txn.id))
    assert entry.executed
    assert entry.execution_method is ExecutionMethod.RAZORPAY_API_SIMULATED
    assert entry.payment_link_id and entry.payment_link_id.startswith("plink_SIM")


def test_message_falls_back_to_template_without_llm(txn_factory) -> None:
    txn = txn_factory()
    ex = Executor(SimulatedGateway(), FakeLLM(available=False))
    entry = ex.execute(txn, _decision(txn, DiagnosisAction.SEND_REMINDER), _diag(txn.id))
    assert entry.execution_method is ExecutionMethod.TEMPLATE_MESSAGE
    assert "₹1,000" in entry.detail


def test_message_uses_llm_when_available(txn_factory) -> None:
    txn = txn_factory()
    ex = Executor(
        SimulatedGateway(), FakeLLM(available=True, text="Hi, quick nudge about your order.")
    )
    entry = ex.execute(txn, _decision(txn, DiagnosisAction.REQUEST_UPDATE), _diag(txn.id))
    assert entry.execution_method is ExecutionMethod.LLM_MESSAGE
    assert entry.detail == "Hi, quick nudge about your order."


def test_projected_outcome_is_deterministic_per_transaction() -> None:
    a = project_outcome(DiagnosisAction.RETRY_NOW, "pay_fixed")
    b = project_outcome(DiagnosisAction.RETRY_NOW, "pay_fixed")
    assert a == b
