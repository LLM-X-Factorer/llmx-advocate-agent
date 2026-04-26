"""Evaluation primitives: fork a task with overrides, compare outputs.

Forking copies a task's source pack into a brand-new task with overridden
config (e.g. swap llm_model, opening_style). Both tasks share an identical
input contract (the source pack), so any divergence in their phase runs is
attributable to the config delta — that's what `compare_tasks` returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from llmx_advocate.core.models import (
    OpeningStyle,
    PhaseId,
    PhaseRun,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
)
from llmx_advocate.store import repo


@dataclass
class TaskComparison:
    """Side-by-side comparison of two tasks (typically a fork of the same source pack)."""

    a_id: str
    b_id: str
    a_config: dict[str, Any]
    b_config: dict[str, Any]
    a_status: TaskStatus
    b_status: TaskStatus
    a_total_duration_ms: int
    b_total_duration_ms: int
    a_total_input_tokens: int
    b_total_input_tokens: int
    a_total_output_tokens: int
    b_total_output_tokens: int
    phase_summary: list[dict[str, Any]]


async def fork_task(
    session: AsyncSession,
    *,
    source_task_id: str,
    title_suffix: str = "fork",
    llm_model: str | None = None,
    llm_provider: str | None = None,
    opening_style: OpeningStyle | None = None,
) -> Task:
    """Create a new task with the same source pack as `source_task_id`, with
    optional config overrides. The new task starts at P1 — fork doesn't copy
    phase outputs (we want each fork to run from scratch for fair comparison).
    """
    src = await repo.get_task(session, source_task_id)
    if src is None:
        raise ValueError(f"source task {source_task_id} not found")

    cfg_dict = src.config.model_dump()
    if llm_model is not None:
        cfg_dict["llm_model"] = llm_model
    if llm_provider is not None:
        cfg_dict["llm_provider"] = llm_provider
    if opening_style is not None:
        cfg_dict["opening_style"] = opening_style
    new_cfg = TaskConfig.model_validate(cfg_dict)

    return await repo.create_task(
        session,
        title=f"{src.title} ({title_suffix})",
        source=src.source.model_copy(),
        config=new_cfg,
    )


async def compare_tasks(session: AsyncSession, a_id: str, b_id: str) -> TaskComparison:
    """Phase-by-phase comparison of two tasks.

    The output is intentionally lightweight: the per-phase summary lists
    status / duration / token counts for each side. Detailed output diffs
    live in PhaseRun records and can be fetched on demand.
    """
    a = await repo.get_task(session, a_id)
    b = await repo.get_task(session, b_id)
    if a is None or b is None:
        raise ValueError(f"task missing (a={a_id}, b={b_id})")

    a_runs = await repo.list_phase_runs(session, a_id)
    b_runs = await repo.list_phase_runs(session, b_id)

    phase_summary: list[dict[str, Any]] = []
    for pid in PhaseId:
        a_runs_for = [r for r in a_runs if r.phase_id == pid]
        b_runs_for = [r for r in b_runs if r.phase_id == pid]
        if not a_runs_for and not b_runs_for:
            continue
        phase_summary.append({
            "phase": pid.value,
            "a": _phase_run_summary(a_runs_for),
            "b": _phase_run_summary(b_runs_for),
        })

    return TaskComparison(
        a_id=a_id,
        b_id=b_id,
        a_config=a.config.model_dump(),
        b_config=b.config.model_dump(),
        a_status=a.status,
        b_status=b.status,
        a_total_duration_ms=sum(r.duration_ms for r in a_runs),
        b_total_duration_ms=sum(r.duration_ms for r in b_runs),
        a_total_input_tokens=sum(r.cost.input_tokens for r in a_runs),
        b_total_input_tokens=sum(r.cost.input_tokens for r in b_runs),
        a_total_output_tokens=sum(r.cost.output_tokens for r in a_runs),
        b_total_output_tokens=sum(r.cost.output_tokens for r in b_runs),
        phase_summary=phase_summary,
    )


def _phase_run_summary(runs: list[PhaseRun]) -> dict[str, Any]:
    if not runs:
        return {"status": "missing", "attempts": 0, "duration_ms": 0}
    last = runs[-1]
    return {
        "status": last.status.value,
        "attempts": len(runs),
        "duration_ms": sum(r.duration_ms for r in runs),
        "input_tokens": sum(r.cost.input_tokens for r in runs),
        "output_tokens": sum(r.cost.output_tokens for r in runs),
        "qa_passed": (
            last.qa_result.passed_overall if last.qa_result else None
        ),
    }


def diff_against_config(a_cfg: dict, b_cfg: dict) -> dict[str, dict]:
    """Return the keys where two TaskConfig dicts differ — useful for
    summarising what makes a fork different from its source.
    """
    diffs = {}
    for k in set(a_cfg) | set(b_cfg):
        av = a_cfg.get(k)
        bv = b_cfg.get(k)
        if av != bv:
            diffs[k] = {"a": av, "b": bv}
    return diffs


def make_source_input_for_fork(src: SourceInput, *, persist_content_inline: bool = True) -> SourceInput:
    """Materialise the source so the fork doesn't rely on an external file path
    that might disappear. By default we keep content inline."""
    if src.pack_content:
        return SourceInput(pack_content=src.pack_content)
    if src.pack_path and persist_content_inline:
        from pathlib import Path
        return SourceInput(pack_content=Path(src.pack_path).read_text(encoding="utf-8"))
    return src.model_copy()
