"""`revenue-recovery` -- the command-line entry point."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from revenue_recovery import __version__
from revenue_recovery.app import load_report, run_pipeline, save_report
from revenue_recovery.config import get_settings
from revenue_recovery.domain.results import PipelineReport
from revenue_recovery.logging import configure

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
    console.print(f"revenue-recovery-agent {__version__}")


@app.command()
def run(
    count: int = typer.Option(180, help="Batch size to generate."),
    seed: int = typer.Option(42, help="RNG seed -- same seed, identical batch."),
    inject_failure: bool = typer.Option(
        False, "--inject-failure", help="Add one malformed record to exercise containment."
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

    report = run_pipeline(count=count, seed=seed, inject_failure=inject_failure, settings=settings)
    path = save_report(report, settings)
    _render_summary(report, verbose=not quiet)
    console.print(f"\n[dim]report written to[/] {path}")


@app.command()
def report() -> None:
    """Re-print the summary of the last run."""
    existing = load_report()
    if existing is None:
        console.print("[yellow]No report yet. Run:[/] revenue-recovery run")
        raise typer.Exit(1)
    _render_summary(existing, verbose=True)


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
    uvicorn.run("revenue_recovery.api.main:app", host=host, port=port, reload=reload)


@app.command()
def demo(
    inject_failure: bool = typer.Option(False, "--inject-failure"),
    serve_after: bool = typer.Option(True, "--serve/--no-serve", help="Serve the SPA when done."),
) -> None:
    """One-shot: run the pipeline, then serve the dashboard."""
    run(count=180, seed=42, inject_failure=inject_failure, live_links=None, quiet=False)
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
    headline.add_row("Executed / blocked", f"{s.executed_actions} / {s.blocked_actions}")
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
    if report.summary.failed:
        headline.add_row("[red]Failed (contained)[/]", f"[red]{report.summary.failed}[/]")

    console.print(
        Panel(
            headline, title=f"run {report.run_id}  ·  {report.duration_ms} ms", border_style="green"
        )
    )

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
