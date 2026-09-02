"""Full pipeline: diagnose -> decide -> execute, with containment."""

from __future__ import annotations

from recover_ai.adapters.synthetic import generate_batch
from recover_ai.app import run_pipeline
from recover_ai.config import get_settings
from recover_ai.services.diagnosis import DiagnosisEngine
from recover_ai.services.recovery import RecoveryEngine
from tests.conftest import FakeLLM


def test_normal_batch_completes_with_no_failures() -> None:
    report = run_pipeline(count=150, seed=42, settings=get_settings())
    assert report.summary.failed == 0
    assert report.summary.completed == report.summary.needing_attention


def test_poisoned_record_fails_alone_and_the_batch_continues() -> None:
    baseline = run_pipeline(count=150, seed=42).summary.completed
    report = run_pipeline(count=150, seed=42, inject_failure=True)

    failed = [r for r in report.results if r.stage_reached == "failed"]
    assert len(failed) == 1
    assert failed[0].transaction_id == "pay_POISONED_DEMO"
    assert "not-a-number" in (failed[0].error or "")
    # every other transaction processed exactly as before
    assert report.summary.completed == baseline


def test_failed_result_still_carries_an_audit_entry() -> None:
    report = run_pipeline(count=60, seed=1, inject_failure=True)
    poisoned = next(r for r in report.results if r.transaction_id == "pay_POISONED_DEMO")
    assert poisoned.audit_entry.execution_method.value == "pipeline_error"
    assert poisoned.audit_entry.executed is False


def test_compliance_invariant_holds_across_a_fresh_large_batch() -> None:
    """On any seed, a do_not_contact diagnosis must never yield an action."""
    txns = generate_batch(count=400, seed=99)
    diagnoser = DiagnosisEngine(FakeLLM(available=False))
    engine = RecoveryEngine()
    ordered = sorted((t for t in txns if t.needs_attention), key=lambda t: t.created_at)
    violations = []
    for txn in ordered:
        diag = diagnoser.diagnose(txn)
        decision = engine.decide(txn, diag)
        if diag.action.value == "do_not_contact" and decision.final_action is not None:
            violations.append(txn.id)
    assert violations == []


def test_report_is_json_roundtrippable() -> None:
    from recover_ai.domain.results import PipelineReport

    report = run_pipeline(count=80, seed=3)
    restored = PipelineReport.model_validate_json(report.model_dump_json())
    assert restored.summary.projected_recovered == report.summary.projected_recovered
    assert restored.learning == report.learning
    assert restored.policy_version == report.policy_version


def test_holdout_creates_a_control_group_and_a_lift_number() -> None:
    report = run_pipeline(count=200, seed=42)
    s = report.summary
    assert s.held_out_actions > 0
    assert s.causal.control_n == s.held_out_actions
    assert s.causal.treatment_n == s.executed_actions
    # treated customers convert better than the untouched control
    assert s.causal.treatment_rate > s.causal.control_rate
    # held-out actions are decided but never executed
    held = [r for r in report.results if r.audit_entry.held_out]
    assert all(not r.audit_entry.executed for r in held)
    assert all(r.decision is not None for r in held)


def test_learning_loop_warm_starts_and_records_predictions() -> None:
    report = run_pipeline(count=120, seed=7)
    assert report.learning is not None
    assert report.learning["observations"] > 0
    assert 0.0 < float(report.learning["brier_score"]) < 1.0  # a real calibration score
    # every executed action carries the posterior rate it was scored with
    acted = [r.audit_entry for r in report.results if r.audit_entry.executed]
    assert acted and all(e.predicted_rate is not None for e in acted)
    assert all(e.conversion_key and e.net_expected_value is not None for e in acted)


def test_shadow_mode_executes_nothing() -> None:
    report = run_pipeline(count=100, seed=42, mode="shadow")
    assert report.mode == "shadow"
    methods = report.summary.execution_methods
    assert methods.get("shadow", 0) > 0
    assert report.summary.executed_actions == 0
    # a shadow run does not overwrite the saved report or learning state
    assert "razorpay_api" not in methods


def test_negative_ev_recoveries_are_skipped_not_executed() -> None:
    # a policy that demands a very high NEV floor -> most small recoveries skipped
    from recover_ai.adapters.factory import build_llm, build_payment_gateway
    from recover_ai.adapters.synthetic import generate_batch
    from recover_ai.domain.policy import Policy
    from recover_ai.services.pipeline import Pipeline

    settings = get_settings()
    policy = Policy(min_net_expected_value=5000.0)
    pipe = Pipeline(
        settings=settings,
        llm=build_llm(settings),
        gateway=build_payment_gateway(settings),
        policy=policy,
    )
    report = pipe.run(generate_batch(150, 42), seed=42, count=150)
    assert report.summary.economics.skipped_negative_ev > 0
