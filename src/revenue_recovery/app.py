"""Application wiring: build a Pipeline from Settings, run it, persist it."""

from __future__ import annotations

import json
from pathlib import Path

from revenue_recovery.adapters.factory import build_llm, build_payment_gateway
from revenue_recovery.adapters.synthetic import generate_batch
from revenue_recovery.config import Settings, get_settings
from revenue_recovery.domain.results import PipelineReport
from revenue_recovery.services.pipeline import Pipeline, inject_poison_transaction

REPORT_FILENAME = "pipeline_report.json"


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    settings = settings or get_settings()
    return Pipeline(
        settings=settings,
        llm=build_llm(settings),
        gateway=build_payment_gateway(settings),
    )


def run_pipeline(
    *,
    count: int = 180,
    seed: int = 42,
    inject_failure: bool = False,
    settings: Settings | None = None,
) -> PipelineReport:
    settings = settings or get_settings()
    pipeline = build_pipeline(settings)

    transactions = generate_batch(count, seed)
    if inject_failure:
        transactions = inject_poison_transaction(transactions)

    return pipeline.run(transactions, seed=seed, count=count, failure_injected=inject_failure)


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
