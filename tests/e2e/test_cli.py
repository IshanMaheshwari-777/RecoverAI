from __future__ import annotations

from typer.testing import CliRunner

from revenue_recovery.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "revenue-recovery-agent" in result.stdout


def test_run_writes_a_report_and_prints_the_headline() -> None:
    result = runner.invoke(app, ["run", "--count", "80", "--seed", "42", "--quiet"])
    assert result.exit_code == 0, result.output
    assert "At-risk revenue" in result.output
    assert "Compliance violations" in result.output

    # report command re-reads it
    again = runner.invoke(app, ["report"])
    assert again.exit_code == 0
    assert "run " in again.output


def test_report_without_a_run_exits_nonzero() -> None:
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 1


def test_run_with_injected_failure_is_contained() -> None:
    result = runner.invoke(
        app, ["run", "--count", "80", "--seed", "42", "--inject-failure", "--quiet"]
    )
    assert result.exit_code == 0
    assert "Failed (contained)" in result.output
