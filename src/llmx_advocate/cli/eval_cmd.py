from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from llmx_advocate.cli.api_client import APIError, call

console = Console()


def _abort(msg: str) -> None:
    console.print(f"[bold red]{msg}[/bold red]")
    raise click.Abort()


@click.group(help="Evaluation commands — A/B compare across model × opening_style.")
def eval_group() -> None:
    pass


@eval_group.command("fork")
@click.argument("source_task_id")
@click.option("--model", default=None, help="Override generation-side llm_model.")
@click.option("--provider", default=None, help="Override generation-side llm_provider.")
@click.option(
    "--opening-style",
    type=click.Choice(["judgment_first", "suspense_first", "auto"]),
    default=None,
)
@click.option("--title-suffix", default="fork")
@click.option("--no-run", is_flag=True, help="Create the fork without running it.")
@click.option("--async", "run_async", is_flag=True, help="Hand off to Celery instead of running inline.")
def eval_fork(source_task_id, model, provider, opening_style, title_suffix, no_run, run_async) -> None:
    """Fork a task with overridden config and (optionally) run it."""
    payload = {
        "title_suffix": title_suffix,
        "llm_model": model,
        "llm_provider": provider,
        "opening_style": opening_style,
        "run_immediately": not no_run,
        "run_async": run_async,
    }
    try:
        data = call("POST", f"/eval/fork/{source_task_id}", json=payload)
    except APIError as e:
        _abort(str(e))

    task = data["task"]
    console.print(f"[green]forked[/green] {source_task_id[:12]} → {task['id']}")
    console.print(f"  status: {task['status']}")
    console.print(f"  current phase: {task['current_phase']}")


@eval_group.command("compare")
@click.argument("task_a_id")
@click.argument("task_b_id")
def eval_compare(task_a_id, task_b_id) -> None:
    """Side-by-side compare two task runs (typically a fork pair)."""
    try:
        data = call("GET", "/eval/compare", params={"a": task_a_id, "b": task_b_id})
    except APIError as e:
        _abort(str(e))

    cmp = data["comparison"]
    diff = data["config_diff"]

    console.rule(f"{task_a_id[:12]}  vs  {task_b_id[:12]}")
    console.print()
    if diff:
        diff_table = Table(title="Config delta")
        diff_table.add_column("field")
        diff_table.add_column("A")
        diff_table.add_column("B")
        for k, v in diff.items():
            diff_table.add_row(k, str(v.get("a"))[:40], str(v.get("b"))[:40])
        console.print(diff_table)
    else:
        console.print("[dim]configs are identical[/dim]")
    console.print()

    summary = Table(title="Phase summary")
    summary.add_column("Phase", style="cyan")
    summary.add_column("A status")
    summary.add_column("A attempts", justify="right")
    summary.add_column("A duration", justify="right")
    summary.add_column("A tokens", justify="right")
    summary.add_column("B status")
    summary.add_column("B attempts", justify="right")
    summary.add_column("B duration", justify="right")
    summary.add_column("B tokens", justify="right")

    for row in cmp["phase_summary"]:
        a, b = row["a"], row["b"]
        summary.add_row(
            row["phase"],
            a["status"],
            str(a["attempts"]),
            f"{a['duration_ms']}ms",
            str(a.get("input_tokens", 0) + a.get("output_tokens", 0)),
            b["status"],
            str(b["attempts"]),
            f"{b['duration_ms']}ms",
            str(b.get("input_tokens", 0) + b.get("output_tokens", 0)),
        )
    console.print(summary)
    console.print()

    totals = Table(title="Totals")
    totals.add_column("metric")
    totals.add_column("A")
    totals.add_column("B")
    totals.add_row("status", cmp["a_status"], cmp["b_status"])
    totals.add_row("duration_ms", str(cmp["a_total_duration_ms"]), str(cmp["b_total_duration_ms"]))
    totals.add_row(
        "input_tokens",
        str(cmp["a_total_input_tokens"]),
        str(cmp["b_total_input_tokens"]),
    )
    totals.add_row(
        "output_tokens",
        str(cmp["a_total_output_tokens"]),
        str(cmp["b_total_output_tokens"]),
    )
    console.print(totals)


@eval_group.command("batch")
@click.option("--source", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--models", required=True, help="Comma-separated model list.")
@click.option("--opening-styles", default="auto", help="Comma-separated styles.")
@click.option("--title", default="eval batch")
@click.option("--no-async", is_flag=True, help="Run inline instead of via Celery.")
def eval_batch(source, models, opening_styles, title, no_async) -> None:
    """Spawn one task per (model × opening_style) pair from the same source pack."""
    pack_text = Path(source).read_text(encoding="utf-8")
    payload = {
        "source_pack_content": pack_text,
        "title": title,
        "models": [m.strip() for m in models.split(",") if m.strip()],
        "opening_styles": [s.strip() for s in opening_styles.split(",") if s.strip()],
        "run_async": not no_async,
    }
    try:
        data = call("POST", "/eval/batch", json=payload)
    except APIError as e:
        _abort(str(e))

    console.print(f"[green]created[/green] {len(data['task_ids'])} tasks")
    for tid in data["task_ids"]:
        console.print(f"  {tid}")
