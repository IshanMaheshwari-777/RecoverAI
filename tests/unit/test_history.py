"""The SQLite run ledger -- a real, queryable history, not one overwritten file."""

from __future__ import annotations

from recover_ai.app import run_pipeline
from recover_ai.services.history import list_runs, record_run


def test_empty_ledger_returns_no_rows(tmp_path) -> None:
    assert list_runs(tmp_path) == []


def test_record_and_list_a_run(tmp_path) -> None:
    report = run_pipeline(count=60, seed=1)
    record_run(report, tmp_path)

    rows = list_runs(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == report.run_id
    assert row["mode"] == "live"
    assert row["data_source"] == "synthetic"
    assert row["total_transactions"] == report.summary.total_transactions
    assert row["at_risk_rupees"] == float(report.summary.at_risk.rupees)


def test_re_recording_the_same_run_replaces_it(tmp_path) -> None:
    report = run_pipeline(count=40, seed=2)
    record_run(report, tmp_path)
    record_run(report, tmp_path)  # idempotent -- same run_id, one row
    assert len(list_runs(tmp_path)) == 1


def test_history_orders_newest_first(tmp_path) -> None:
    a = run_pipeline(count=30, seed=3)
    b = run_pipeline(count=30, seed=4)
    record_run(a, tmp_path)
    record_run(b, tmp_path)
    rows = list_runs(tmp_path)
    assert len(rows) == 2
    assert {r["run_id"] for r in rows} == {a.run_id, b.run_id}


def test_list_respects_limit(tmp_path) -> None:
    for i in range(5):
        record_run(run_pipeline(count=20, seed=i), tmp_path)
    assert len(list_runs(tmp_path, limit=2)) == 2
