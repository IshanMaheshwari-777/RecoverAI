"""A durable ledger of every run.

`data/pipeline_report.json` holds exactly one report -- the latest run
overwrites it, because that's what the live dashboard renders. This is
the other half: a small SQLite database (stdlib, no new infra) that keeps
one row per run forever, so "how has recovery performed over time" is an
answerable question instead of something only the most recent run knows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from recover_ai.domain.results import PipelineReport

HISTORY_FILENAME = "recover.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    data_source TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    total_transactions INTEGER NOT NULL,
    needing_attention INTEGER NOT NULL,
    executed_actions INTEGER NOT NULL,
    held_out_actions INTEGER NOT NULL,
    at_risk_rupees REAL NOT NULL,
    projected_recovered_rupees REAL NOT NULL,
    confirmed_recovered_rupees REAL NOT NULL,
    incremental_lift REAL NOT NULL,
    compliance_violations INTEGER NOT NULL
)
"""


def _db_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / HISTORY_FILENAME


def record_run(report: PipelineReport, data_dir: str | Path) -> None:
    path = _db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment = report.learning.get("experiment") if report.learning else None
    incremental = (
        float(experiment.get("incremental_rate", 0.0)) if isinstance(experiment, dict) else 0.0
    )

    con = sqlite3.connect(path)
    try:
        con.execute(_SCHEMA)
        con.execute(
            """INSERT OR REPLACE INTO runs (
                run_id, started_at, finished_at, mode, data_source, policy_version,
                total_transactions, needing_attention, executed_actions, held_out_actions,
                at_risk_rupees, projected_recovered_rupees, confirmed_recovered_rupees,
                incremental_lift, compliance_violations
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                report.run_id,
                report.started_at.isoformat(),
                report.finished_at.isoformat(),
                report.mode,
                report.data_source,
                report.policy_version,
                report.summary.total_transactions,
                report.summary.needing_attention,
                report.summary.executed_actions,
                report.summary.held_out_actions,
                float(report.summary.at_risk.rupees),
                float(report.summary.projected_recovered.rupees),
                float(report.summary.confirmed_recovered.rupees),
                incremental,
                report.summary.compliance_violations,
            ),
        )
        con.commit()
    finally:
        con.close()


def list_runs(data_dir: str | Path, *, limit: int = 20) -> list[dict[str, object]]:
    path = _db_path(data_dir)
    if not path.exists():
        return []
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        con.execute(_SCHEMA)
        rows = con.execute(
            "SELECT * FROM runs ORDER BY finished_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()
