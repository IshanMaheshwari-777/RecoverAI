"""Full pipeline: diagnose -> decide -> execute, with containment."""

from __future__ import annotations

from revenue_recovery.adapters.synthetic import generate_batch
from revenue_recovery.app import run_pipeline
from revenue_recovery.config import get_settings
from revenue_recovery.services.diagnosis import DiagnosisEngine
from revenue_recovery.services.recovery import RecoveryEngine
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
    from revenue_recovery.domain.results import PipelineReport

    report = run_pipeline(count=80, seed=3)
    restored = PipelineReport.model_validate_json(report.model_dump_json())
    assert restored.summary.projected_recovered == report.summary.projected_recovered
