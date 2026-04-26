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


@click.group(help="Task lifecycle commands.")
def task_group() -> None:
    pass


@task_group.command("new")
@click.argument("pack_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--title", default=None, help="Task title; defaults to pack file stem.")
@click.option("--audience", type=click.Choice(["学生", "从业者", "决策者"]), default="决策者")
@click.option("--tier", type=click.Choice(["引流", "留存", "转化", "auto"]), default="auto")
@click.option(
    "--opening-style",
    type=click.Choice(["judgment_first", "suspense_first", "auto"]),
    default="auto",
)
@click.option("--model", default=None, help="Generation-side LLM model. Default: settings.")
def task_new(pack_path, title, audience, tier, opening_style, model) -> None:
    """Create a task from a source pack file (markdown + YAML frontmatter).

    See docs/source-pack-schema.md. Need to author one by hand?
    Copy tests/fixtures/example-pack/manual-pack-example.md.
    """
    pack_text = Path(pack_path).read_text(encoding="utf-8")
    config: dict = {
        "target_audience": audience,
        "target_tier": tier,
        "opening_style": opening_style,
    }
    if model:
        config["llm_model"] = model

    payload = {
        "title": title or Path(pack_path).stem,
        "source": {"pack_content": pack_text},
        "config": config,
    }

    try:
        data = call("POST", "/tasks", json=payload)
    except APIError as e:
        _abort(str(e))

    _print_task_detail(data)


@task_group.command("list")
@click.option("--status", default=None, help="Filter by status.")
@click.option("--limit", default=20, show_default=True)
def task_list(status, limit) -> None:
    try:
        data = call("GET", "/tasks", params={"status": status, "limit": limit} if status else {"limit": limit})
    except APIError as e:
        _abort(str(e))

    table = Table(title="Tasks")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Phase")
    table.add_column("Status")
    table.add_column("Created")
    for t in data:  # type: ignore[union-attr]
        table.add_row(
            t["id"],
            t["title"][:40],
            t["current_phase"],
            t["status"],
            t["created_at"][:19].replace("T", " "),
        )
    console.print(table)


@task_group.command("show")
@click.argument("task_id")
def task_show(task_id) -> None:
    try:
        data = call("GET", f"/tasks/{task_id}")
    except APIError as e:
        _abort(str(e))
    _print_task_detail(data)


@task_group.command("run")
@click.argument("task_id")
def task_run(task_id) -> None:
    try:
        data = call("POST", f"/tasks/{task_id}/actions/run")
    except APIError as e:
        _abort(str(e))
    _print_task_detail(data)


@task_group.command("pause")
@click.argument("task_id")
def task_pause(task_id) -> None:
    try:
        call("POST", f"/tasks/{task_id}/actions/pause")
    except APIError as e:
        _abort(str(e))
    console.print(f"[green]paused[/green] {task_id}")


@task_group.command("resume")
@click.argument("task_id")
def task_resume(task_id) -> None:
    """Alias for `run` — resumes a paused task."""
    try:
        data = call("POST", f"/tasks/{task_id}/actions/run")
    except APIError as e:
        _abort(str(e))
    _print_task_detail(data)


@task_group.command("step")
@click.argument("task_id")
def task_step(task_id) -> None:
    console.print("[yellow]step[/yellow] not implemented yet — use `task run` instead.")


@task_group.command("edit")
@click.argument("task_id")
@click.argument("phase")
def task_edit(task_id, phase) -> None:
    console.print("[yellow]edit[/yellow] not implemented yet (planned in M3).")


@task_group.command("qa")
@click.argument("task_id")
@click.argument("phase")
def task_qa(task_id, phase) -> None:
    console.print("[yellow]qa rerun[/yellow] not implemented yet (planned in M3).")


@task_group.command("export")
@click.argument("task_id")
@click.option("--out", default=".")
def task_export(task_id, out) -> None:
    console.print("[yellow]export[/yellow] not implemented yet (planned in M3).")


@task_group.command("fork")
@click.argument("task_id")
@click.option("--model", required=True)
@click.option(
    "--opening-style",
    type=click.Choice(["judgment_first", "suspense_first", "auto"]),
    default=None,
)
def task_fork(task_id, model, opening_style) -> None:
    console.print(
        "[yellow]fork[/yellow] not implemented yet (planned in M3 — needs eval scaffolding)."
    )


def _print_task_detail(data) -> None:  # type: ignore[no-untyped-def]
    task = data["task"]
    runs = data.get("runs", [])

    console.print()
    console.rule(f"[bold cyan]{task['id']}[/bold cyan] — {task['title']}")
    console.print(f"status:        [bold]{task['status']}[/bold]")
    console.print(f"current phase: [bold]{task['current_phase']}[/bold]")
    console.print(f"created at:    {task['created_at']}")

    if not runs:
        return

    table = Table(title="Phase runs", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Phase", style="cyan")
    table.add_column("Attempt", justify="right")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("QA")

    for i, r in enumerate(runs, 1):
        qa_summary = "—"
        if r.get("qa_result"):
            gates = r["qa_result"].get("gates", [])
            ok = sum(1 for g in gates if g.get("passed"))
            qa_summary = f"{ok}/{len(gates)}"
        status = r["status"]
        status_styled = _style_status(status)
        table.add_row(
            str(i),
            r["phase_id"],
            str(r["attempt"]),
            status_styled,
            f"{r['duration_ms']}ms",
            qa_summary,
        )
    console.print(table)

    last = runs[-1]
    if last["status"] == "error":
        console.print()
        console.print(
            "[yellow]Last phase errored.[/yellow] "
            "If this was a stub phase (NotImplementedError), it's expected — "
            "the engine paused for human."
        )


def _style_status(status: str) -> str:
    if status == "passed":
        return "[green]passed[/green]"
    if status in ("qa_failed", "qa_failed_terminal"):
        return f"[red]{status}[/red]"
    if status == "error":
        return "[yellow]error[/yellow]"
    return status
