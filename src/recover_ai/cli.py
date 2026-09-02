"""`recover-ai` -- the command-line entry point."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from recover_ai import __version__
from recover_ai.app import build_pipeline, load_report, run_pipeline, save_report
from recover_ai.config import get_settings
from recover_ai.domain.policy import Policy
from recover_ai.domain.results import PipelineReport
from recover_ai.logging import configure

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Diagnose failed Razorpay payments and drive compliant, bounded recovery.",
)
console = Console()


def _bootstrap() -> None:
    s = get_settings()
    configure(json_logs=s.log_json, level=s.log_level)


@app.callback()
def _main() -> None:
    _bootstrap()


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"recover-ai {__version__}")


@app.command()
def run(
    count: int = typer.Option(180, help="Batch size to generate."),
    seed: int = typer.Option(42, help="RNG seed -- same seed, identical batch."),
    inject_failure: bool = typer.Option(
        False, "--inject-failure", help="Add one malformed record to exercise containment."
    ),
    shadow: bool = typer.Option(
        False, "--shadow", help="Decide everything, execute nothing -- a dry run."
    ),
    live_links: int | None = typer.Option(
        None, help="Cap on genuinely-live Razorpay link creations (default from settings)."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only print the summary."),
) -> None:
    """Run the full pipeline and write data/pipeline_report.json."""
    settings = get_settings()
    if live_links is not None:
        settings.live_link_budget = live_links

    console.print(Panel.fit(settings.credential_banner(), title="credentials", border_style="cyan"))

    mode = "shadow" if shadow else "live"
    report = run_pipeline(
        count=count, seed=seed, inject_failure=inject_failure, mode=mode, settings=settings
    )
    _render_summary(report, verbose=not quiet)
    if not shadow:
        path = save_report(report, settings)
        console.print(f"\n[dim]report written to[/] {path}")
    else:
        console.print("\n[yellow]shadow run -- nothing executed, report not saved[/]")


@app.command()
def report() -> None:
    """Re-print the summary of the last run."""
    existing = load_report()
    if existing is None:
        console.print("[yellow]No report yet. Run:[/] recover-ai run")
        raise typer.Exit(1)
    _render_summary(existing, verbose=True)


@app.command()
def backtest(
    csv_path: str = typer.Argument(
        ..., help="CSV of past failures with an actual_recovered column."
    ),
    policy_file: str | None = typer.Option(None, "--policy", help="policy.toml to replay."),
) -> None:
    """Replay a policy over a historical outcome log and report the lift."""
    from recover_ai.adapters.factory import build_llm
    from recover_ai.services.backtest import run_backtest

    settings = get_settings()
    policy = (
        Policy.load(Path(policy_file).parent) if policy_file else Policy.load(settings.data_dir)
    )
    result = run_backtest(csv_path, policy, build_llm(settings))

    t = Table.grid(padding=(0, 3))
    t.add_column(justify="right", style="bold")
    t.add_column()
    t.add_row("Rows replayed", str(result.rows))
    t.add_row(
        "Would act / skip (low EV) / blocked",
        f"{result.would_act} / {result.skipped_negative_ev} / {result.blocked}",
    )
    t.add_row("Actually recovered", str(result.actual_recovered_revenue))
    t.add_row("Policy projects", str(result.projected_recovered_revenue))
    t.add_row("Organic baseline", str(result.organic_recovered_revenue))
    t.add_row("Incremental (vs. organic)", str(result.incremental_revenue))
    t.add_row("Calibration (Brier)", f"{result.brier_score:.4f}")
    console.print(Panel(t, title=f"backtest · {policy.version}", border_style="cyan"))


@app.command("policy-diff")
def policy_diff(
    policy_a: str = typer.Argument(..., help="Directory containing the baseline policy.toml."),
    policy_b: str = typer.Argument(..., help="Directory containing the candidate policy.toml."),
    count: int = typer.Option(200, help="Batch size."),
    seed: int = typer.Option(42),
) -> None:
    """Run two policies in shadow over the same batch and diff the outcomes."""
    from recover_ai.adapters.synthetic import generate_batch

    settings = get_settings()
    batch = generate_batch(count, seed)

    def shadow_run(policy: Policy) -> PipelineReport:
        pipe = build_pipeline(settings)
        pipe.policy = policy
        return pipe.run(batch, seed=seed, count=count, mode="shadow")

    a = shadow_run(Policy.load(policy_a))
    b = shadow_run(Policy.load(policy_b))

    t = Table(show_header=True, header_style="dim")
    t.add_column("metric")
    t.add_column(a.policy_version, justify="right")
    t.add_column(b.policy_version, justify="right")
    t.add_column("Δ", justify="right")

    def fmt(v: float, money: bool) -> str:
        return f"₹{v:,.0f}" if money else f"{v:g}"

    def row(label: str, x: float, y: float, money: bool = False) -> None:
        delta = y - x
        colour = "green" if delta >= 0 else "red"
        t.add_row(label, fmt(x, money), fmt(y, money), f"[{colour}]{fmt(delta, money)}[/]")

    row(
        "Would execute",
        a.summary.executed_actions or a.summary.execution_methods.get("shadow", 0),
        b.summary.executed_actions or b.summary.execution_methods.get("shadow", 0),
    )
    row(
        "Skipped (low EV)",
        a.summary.economics.skipped_negative_ev,
        b.summary.economics.skipped_negative_ev,
    )
    row("Held out", a.summary.held_out_actions, b.summary.held_out_actions)
    row(
        "Projected recovered",
        float(a.summary.projected_recovered.rupees),
        float(b.summary.projected_recovered.rupees),
        money=True,
    )
    row(
        "Channel cost",
        a.summary.economics.total_channel_cost,
        b.summary.economics.total_channel_cost,
        money=True,
    )
    console.print(t)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Serve the JSON API and the dashboard SPA."""
    import uvicorn

    console.print(f"[green]Dashboard[/] -> http://{host}:{port}")
    console.print(f"[green]API docs[/]  -> http://{host}:{port}/docs")
    uvicorn.run("recover_ai.api.main:app", host=host, port=port, reload=reload)


@app.command()
def demo(
    inject_failure: bool = typer.Option(False, "--inject-failure"),
    serve_after: bool = typer.Option(True, "--serve/--no-serve", help="Serve the SPA when done."),
) -> None:
    """One-shot: run the pipeline, then serve the dashboard."""
    run(
        count=180,
        seed=42,
        inject_failure=inject_failure,
        shadow=False,
        live_links=None,
        quiet=False,
    )
    if serve_after:
        serve(host="127.0.0.1", port=8000, reload=False)


# -- rendering --------------------------------------------------------
def _render_summary(report: PipelineReport, *, verbose: bool) -> None:
    s = report.summary
    headline = Table.grid(padding=(0, 3))
    headline.add_column(justify="right", style="bold")
    headline.add_column()
    headline.add_row("At-risk revenue", str(s.at_risk))
    headline.add_row("Projected recovered", f"{s.projected_recovered}  ({s.recovery_rate:.1%})")
    headline.add_row("Confirmed recovered", f"{s.confirmed_recovered}  (awaiting webhooks)")
    if s.causal.control_n:
        headline.add_row(
            "Incremental lift (vs. holdout)",
            f"{s.causal.incremental_rate:.1%}  "
            f"(treated {s.causal.treatment_rate:.0%} / control {s.causal.control_rate:.0%})",
        )
    headline.add_row(
        "Executed / blocked / held out",
        f"{s.executed_actions} / {s.blocked_actions} / {s.held_out_actions}",
    )
    headline.add_row("Skipped (negative EV)", str(s.economics.skipped_negative_ev))
    headline.add_row("Net expected value", f"₹{s.economics.net_expected_value:,.0f}")
    headline.add_row("Escalated (retry cap hit)", str(s.escalated_actions))
    headline.add_row(
        "Compliance violations",
        f"[green]{s.compliance_violations}[/]"
        if not s.compliance_violations
        else f"[red]{s.compliance_violations}[/]",
    )
    headline.add_row(
        "Diagnosis split",
        f"{s.diagnosis_split.rule} rule / {s.diagnosis_split.llm} LLM / "
        f"{s.diagnosis_split.llm_fallback} fallback",
    )
    if report.learning is not None:
        headline.add_row(
            "Learning",
            f"{report.learning['observations']} obs · Brier {report.learning['brier_score']}",
        )
    if report.incidents:
        headline.add_row(
            "[yellow]Incidents[/]",
            f"[yellow]{len(report.incidents)} degraded rail(s), retries deferred[/]",
        )
    if report.summary.failed:
        headline.add_row("[red]Failed (contained)[/]", f"[red]{report.summary.failed}[/]")

    title = f"run {report.run_id}  ·  {report.duration_ms} ms"
    if report.mode == "shadow":
        title += "  ·  SHADOW"
    console.print(Panel(headline, title=title, border_style="green"))

    if not verbose:
        return

    methods = Table(title="Execution method", show_header=True, header_style="dim")
    methods.add_column("method")
    methods.add_column("count", justify="right")
    for name, n in sorted(s.execution_methods.items(), key=lambda kv: -kv[1]):
        methods.add_row(name, str(n))
    console.print(methods)


if __name__ == "__main__":  # pragma: no cover
    app()
