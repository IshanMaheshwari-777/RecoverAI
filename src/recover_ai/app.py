"""Application wiring: build a Pipeline from Settings, run it, persist it."""

from __future__ import annotations

import json
from pathlib import Path

from recover_ai.adapters.factory import build_llm, build_payment_gateway
from recover_ai.adapters.synthetic import (
    generate_batch,
    generate_experiment_history,
    generate_history,
    generate_timing_history,
)
from recover_ai.config import Settings, get_settings
from recover_ai.domain.policy import Policy
from recover_ai.domain.results import PipelineReport
from recover_ai.services.idempotency import load_idempotency, save_idempotency
from recover_ai.services.learning import LearningStore, load_learning, save_learning
from recover_ai.services.pipeline import Pipeline, inject_poison_transaction

REPORT_FILENAME = "pipeline_report.json"


def _load_state(settings: Settings) -> tuple[Policy, LearningStore]:
    policy = Policy.load(settings.data_dir)
    learning = load_learning(policy, settings.data_dir)
    return policy, learning


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    settings = settings or get_settings()
    policy, learning = _load_state(settings)
    return Pipeline(
        settings=settings,
        llm=build_llm(settings),
        gateway=build_payment_gateway(settings),
        policy=policy,
        learning=learning,
        idempotency=load_idempotency(settings.data_dir),
    )


def run_pipeline(
    *,
    count: int = 180,
    seed: int = 42,
    inject_failure: bool = False,
    mode: str = "live",
    warm_start: bool = True,
    settings: Settings | None = None,
) -> PipelineReport:
    settings = settings or get_settings()
    pipeline = build_pipeline(settings)

    learning = pipeline.learning
    if warm_start and learning is not None and learning.summary()["observations"] == 0:
        # Seed the learning loop with deterministic historical outcomes so the
        # calibration curve, posteriors, and causal experiment are meaningful
        # on a fresh install.
        for key, converted, predicted in generate_history(pipeline.policy, seed):
            learning.observe_conversion(key, converted=converted, predicted=predicted)
        for treatment, converted in generate_experiment_history(pipeline.policy, seed):
            learning.observe_experiment(treatment=treatment, converted=converted)
        for reason, hours in generate_timing_history(seed):
            learning.observe_retry_landing(reason, hours)

    transactions = generate_batch(count, seed)
    if inject_failure:
        transactions = inject_poison_transaction(transactions)

    report = pipeline.run(
        transactions, seed=seed, count=count, failure_injected=inject_failure, mode=mode
    )

    if mode == "live":
        if pipeline.learning is not None:
            save_learning(pipeline.learning, settings.data_dir)
        if pipeline.idempotency is not None:
            save_idempotency(pipeline.idempotency, settings.data_dir)
    return report


def report_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return Path(settings.data_dir) / REPORT_FILENAME


def save_report(report: PipelineReport, settings: Settings | None = None) -> Path:
    path = report_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2))
    return path


def load_report(settings: Settings | None = None) -> PipelineReport | None:
    path = report_path(settings)
    if not path.exists():
        return None
    return PipelineReport.model_validate(json.loads(path.read_text()))
