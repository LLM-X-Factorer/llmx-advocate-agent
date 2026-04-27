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
@click.option("--reason", default="", help="Edit note recorded with the new PhaseRun.")
def task_edit(task_id, phase, reason) -> None:
    """Open the latest passed phase output in $EDITOR, then save + re-run QA.

    QA must pass for the edited output to be marked PASSED. Per spec §1, manual
    edits don't bypass gates; if QA fails the new run is recorded as qa_failed
    and the engine treats it like any other retry.
    """
    import json
    import os
    import subprocess
    import tempfile

    try:
        runs = call("GET", f"/tasks/{task_id}/phases/{phase}")
    except APIError as e:
        _abort(str(e))

    passed = [r for r in runs if r["status"] == "passed"]  # type: ignore[index]
    if not passed:
        _abort(f"phase {phase} has no passed run on task {task_id}")
    current_output = passed[-1]["output"]

    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(current_output, tf, ensure_ascii=False, indent=2)
        tf_path = tf.name

    subprocess.run([editor, tf_path], check=True)

    with open(tf_path, encoding="utf-8") as f:
        edited = json.load(f)
    os.unlink(tf_path)

    if edited == current_output:
        console.print("[dim]no changes — skipping save[/dim]")
        return

    try:
        new_run = call("PUT", f"/tasks/{task_id}/phases/{phase}", json={"output": edited, "edit_note": reason})
    except APIError as e:
        _abort(str(e))

    qa = new_run.get("qa_result") or {}  # type: ignore[union-attr]
    overall = qa.get("passed_overall")
    label = "[green]PASSED[/green]" if overall else "[red]QA FAILED[/red]"
    console.print(f"saved edit → {label}")
    if not overall:
        for g in qa.get("gates", []):
            if not g.get("passed"):
                console.print(f"  [red]✗[/red] {g['gate_id']}: {(g.get('rationale') or '')[:120]}")


@task_group.command("qa")
@click.argument("task_id")
@click.argument("phase")
def task_qa(task_id, phase) -> None:
    """Re-run QA gates on the latest passed phase output without re-generating."""
    try:
        run = call("POST", f"/tasks/{task_id}/phases/{phase}/qa")
    except APIError as e:
        _abort(str(e))

    qa = run.get("qa_result") or {}  # type: ignore[union-attr]
    table = Table(title=f"{phase} QA result (rerun)")
    table.add_column("Gate", style="cyan")
    table.add_column("Status")
    table.add_column("Rationale")
    for g in qa.get("gates", []):
        mark = "[green]✓[/green]" if g["passed"] else "[red]✗[/red]"
        table.add_row(g["gate_id"], mark, (g.get("rationale") or "")[:80])
    console.print(table)
    console.print(f"overall: {'[green]PASSED[/green]' if qa.get('passed_overall') else '[red]FAILED[/red]'}")


@task_group.command("export")
@click.argument("task_id")
@click.option("--out", default=".", type=click.Path(file_okay=False), help="Output directory.")
def task_export(task_id, out) -> None:
    """Export the publishable artefacts of a task to a local directory.

    Writes:
      <out>/<task_id>/video.json         — full Video JSON (P4 output)
      <out>/<task_id>/publishing.json    — titles + description + pinned (P6)
      <out>/<task_id>/summary.md         — human-readable digest (judgment / theme / titles)
    """
    import json
    from pathlib import Path

    try:
        data = call("GET", f"/tasks/{task_id}/export")
    except APIError as e:
        _abort(str(e))

    target_dir = Path(out) / task_id
    target_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    if data.get("video_json"):
        path = target_dir / "video.json"
        path.write_text(json.dumps(data["video_json"], ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(path))

    if data.get("publishing"):
        path = target_dir / "publishing.json"
        path.write_text(json.dumps(data["publishing"], ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(path))

    summary_lines = [f"# {data['title']}", "", f"task_id: {data['task_id']}", f"status: {data['status']}"]
    if data.get("tier"):
        summary_lines.append(f"tier: {data['tier']}")
    if data.get("theme"):
        summary_lines += ["", "## Theme", data["theme"]]
    if data.get("judgment"):
        summary_lines += ["", "## Core Judgment", data["judgment"]]
    if data.get("publishing", {}).get("titles"):
        summary_lines += ["", "## Title Options"]
        for i, t in enumerate(data["publishing"]["titles"], 1):
            summary_lines.append(f"{i}. **[{t.get('formula_id', '?')}]** {t['text']}")
            if t.get("rationale"):
                summary_lines.append(f"   - {t['rationale']}")
    if data.get("publishing", {}).get("description"):
        summary_lines += ["", "## Description", data["publishing"]["description"]]
    if data.get("publishing", {}).get("pinned_comment"):
        summary_lines += ["", "## Pinned Comment", "```", data["publishing"]["pinned_comment"], "```"]

    summary_path = target_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    written.append(str(summary_path))

    console.print(f"[green]exported[/green] {task_id} → {target_dir}")
    for p in written:
        console.print(f"  {p}")


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
