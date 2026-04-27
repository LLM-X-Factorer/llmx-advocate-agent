"""Export bundle construction — single source of truth for both
GET /tasks/{id}/export (returns dict) and engine post-completion hook
(writes to OUTPUTS_DIR).

Two bundle shapes:

- ExportBundle: for COMPLETED tasks — video.json + publishing + summary
- FailureBundle: for FAILED tasks — error.md + last failed PhaseRun audit

Output schema is the contract with llmx-advocate-outputs repo, see
docs/output-archive-schema.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from llmx_advocate.core.models import (
    PhaseRun,
    PhaseRunStatus,
    Task,
    TaskStatus,
)


@dataclass
class ExportBundle:
    """Bundle of publishable artefacts for a COMPLETED task.

    Mirrors the TaskExport API response, plus a few fields that only matter
    when persisting to disk (source_pack_id for dedup, completed_at for sort).
    """

    task_id: str
    title: str
    status: str
    source_pack_id: str | None
    judgment: str | None
    theme: str | None
    tier: str | None
    llm_provider: str
    llm_model: str
    created_at: str
    video_json: dict[str, Any] | None = None
    publishing: dict[str, Any] | None = None

    def to_api_dict(self) -> dict[str, Any]:
        """Shape consumed by GET /tasks/{id}/export — backwards-compatible."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "video_json": self.video_json,
            "publishing": self.publishing,
            "judgment": self.judgment,
            "theme": self.theme,
            "tier": self.tier,
        }

    def to_task_json(self) -> dict[str, Any]:
        """Persisted as task.json — the metadata file consumers will join on."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "source_pack_id": self.source_pack_id,
            "tier": self.tier,
            "judgment": self.judgment,
            "theme": self.theme,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "created_at": self.created_at,
        }

    def to_summary_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"- task_id: `{self.task_id}`",
            f"- status: {self.status}",
        ]
        if self.tier:
            lines.append(f"- tier: {self.tier}")
        if self.source_pack_id:
            lines.append(f"- source_pack_id: `{self.source_pack_id}`")
        lines.append(f"- model: `{self.llm_provider}/{self.llm_model}`")
        if self.theme:
            lines += ["", "## Theme", self.theme]
        if self.judgment:
            lines += ["", "## Core Judgment", self.judgment]
        if self.publishing and self.publishing.get("titles"):
            lines += ["", "## Title Options"]
            for i, t in enumerate(self.publishing["titles"], 1):
                formula = t.get("formula_id") or "?"
                lines.append(f"{i}. **[{formula}]** {t['text']}")
                if t.get("rationale"):
                    lines.append(f"   - {t['rationale']}")
        if self.publishing and self.publishing.get("description"):
            lines += ["", "## Description", self.publishing["description"]]
        if self.publishing and self.publishing.get("pinned_comment"):
            lines += ["", "## Pinned Comment", "```", self.publishing["pinned_comment"], "```"]
        return "\n".join(lines) + "\n"


@dataclass
class FailureBundle:
    """Bundle for a FAILED task — captures *why* it failed for post-mortem.

    `last_failed_run` is the run whose status was qa_failed_terminal or error
    that caused the task to enter FAILED. We surface its QA gates, error trail
    and the partial output it produced.
    """

    task_id: str
    title: str
    status: str
    source_pack_id: str | None
    failed_phase: str
    failed_attempts: int
    last_error: str
    last_traceback: str | None
    qa_gates: list[dict[str, Any]] = field(default_factory=list)
    llm_provider: str = ""
    llm_model: str = ""
    created_at: str = ""

    def to_task_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "source_pack_id": self.source_pack_id,
            "failed_phase": self.failed_phase,
            "failed_attempts": self.failed_attempts,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "created_at": self.created_at,
        }

    def to_error_markdown(self) -> str:
        lines = [
            f"# Failure: {self.title}",
            "",
            f"- task_id: `{self.task_id}`",
            f"- failed_phase: `{self.failed_phase}`",
            f"- failed_attempts: {self.failed_attempts}",
        ]
        if self.source_pack_id:
            lines.append(f"- source_pack_id: `{self.source_pack_id}`")
        lines.append(f"- model: `{self.llm_provider}/{self.llm_model}`")

        if self.qa_gates:
            lines += ["", "## QA Gates (last attempt)"]
            for g in self.qa_gates:
                mark = "✅" if g.get("passed") else "❌"
                lines.append(f"- {mark} `{g.get('gate_id')}` — {g.get('rationale', '')}")

        if self.last_error:
            lines += ["", "## Error", "```", self.last_error.strip(), "```"]
        if self.last_traceback:
            lines += ["", "## Traceback", "```", self.last_traceback.strip(), "```"]
        return "\n".join(lines) + "\n"


def _passed_outputs_by_phase(runs: list[PhaseRun]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in runs:
        if r.status == PhaseRunStatus.PASSED:
            out[str(r.phase_id)] = r.output
    return out


def _extract_source_pack_id(by_phase: dict[str, dict[str, Any]]) -> str | None:
    """Pulled from P1's SourcePack output. None if P1 hasn't passed."""
    p1 = by_phase.get("P1") or {}
    pack_id = p1.get("pack_id")
    return pack_id if isinstance(pack_id, str) and pack_id else None


def build_export_bundle(task: Task, runs: list[PhaseRun]) -> ExportBundle:
    """Pure function — given a task and its passed PhaseRuns, build the export
    bundle. Works for any status (returns whatever was produced); callers
    typically only persist when status == COMPLETED.
    """
    by_phase = _passed_outputs_by_phase(runs)
    layer = by_phase.get("P2") or {}
    judgment = by_phase.get("P2.5") or {}
    deep = by_phase.get("P2.6") or {}

    return ExportBundle(
        task_id=task.id,
        title=task.title,
        status=task.status.value,
        source_pack_id=_extract_source_pack_id(by_phase),
        video_json=by_phase.get("P4"),
        publishing=by_phase.get("P6"),
        judgment=judgment.get("full_sentence") if judgment else None,
        theme=deep.get("theme") if deep else None,
        tier=str(layer.get("tier")) if layer.get("tier") else None,
        llm_provider=task.config.llm_provider or "",
        llm_model=task.config.llm_model or "",
        created_at=task.created_at.isoformat() if isinstance(task.created_at, datetime) else str(task.created_at),
    )


def build_failure_bundle(task: Task, runs: list[PhaseRun]) -> FailureBundle:
    """For a task that ended in FAILED status, surface the run that caused it.

    Selection rule: pick the most recent run whose status is one of
    {qa_failed_terminal, error}. That's the run the engine gave up on.
    Falls back to the most recent run if none match (shouldn't happen for
    truly FAILED tasks, but is harmless).
    """
    by_phase = _passed_outputs_by_phase(runs)

    terminal_statuses = {PhaseRunStatus.QA_FAILED_TERMINAL, PhaseRunStatus.ERROR}
    failed_runs = [r for r in runs if r.status in terminal_statuses]
    last = failed_runs[-1] if failed_runs else (runs[-1] if runs else None)

    if last is None:
        return FailureBundle(
            task_id=task.id,
            title=task.title,
            status=task.status.value,
            source_pack_id=_extract_source_pack_id(by_phase),
            failed_phase="(unknown)",
            failed_attempts=0,
            last_error="task failed before any PhaseRun was recorded",
            last_traceback=None,
            llm_provider=task.config.llm_provider or "",
            llm_model=task.config.llm_model or "",
            created_at=task.created_at.isoformat() if isinstance(task.created_at, datetime) else str(task.created_at),
        )

    error_msg = ""
    traceback_str = None
    if isinstance(last.output, dict):
        error_msg = str(last.output.get("_error", ""))
        traceback_str = last.output.get("_traceback")
        if not isinstance(traceback_str, str):
            traceback_str = None
    if not error_msg and last.qa_result and not last.qa_result.passed_overall:
        failed_gates = [g for g in last.qa_result.gates if not g.passed]
        if failed_gates:
            error_msg = "QA gates failed: " + ", ".join(g.gate_id for g in failed_gates)

    qa_gates: list[dict[str, Any]] = []
    if last.qa_result:
        qa_gates = [g.model_dump() for g in last.qa_result.gates]

    return FailureBundle(
        task_id=task.id,
        title=task.title,
        status=task.status.value,
        source_pack_id=_extract_source_pack_id(by_phase),
        failed_phase=str(last.phase_id),
        failed_attempts=last.attempt,
        last_error=error_msg or "(no error message recorded)",
        last_traceback=traceback_str,
        qa_gates=qa_gates,
        llm_provider=last.llm_provider,
        llm_model=last.llm_model,
        created_at=task.created_at.isoformat() if isinstance(task.created_at, datetime) else str(task.created_at),
    )


def persist_to_disk(task: Task, runs: list[PhaseRun], outputs_dir: Path) -> Path | None:
    """Write the bundle for a terminal-status task into the outputs tree.

    - COMPLETED → outputs/YYYY-MM-DD/<task-id>/{task.json, summary.md, video.json, publishing.json, source-pack.md}
    - FAILED → outputs/failures/YYYY-MM-DD/<task-id>/{task.json, error.md, source-pack.md}

    Returns the directory written to, or None if status isn't terminal.

    Files are written atomically (write to .tmp then rename) so concurrent
    git-push readers never see a partial bundle.
    """
    if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        return None

    date_str = task.created_at.date().isoformat() if isinstance(task.created_at, datetime) else "unknown-date"

    if task.status == TaskStatus.COMPLETED:
        target = outputs_dir / date_str / task.id
    else:
        target = outputs_dir / "failures" / date_str / task.id
    target.mkdir(parents=True, exist_ok=True)

    if task.status == TaskStatus.COMPLETED:
        bundle = build_export_bundle(task, runs)
        _atomic_write_json(target / "task.json", bundle.to_task_json())
        _atomic_write_text(target / "summary.md", bundle.to_summary_markdown())
        if bundle.video_json:
            _atomic_write_json(target / "video.json", bundle.video_json)
        if bundle.publishing:
            _atomic_write_json(target / "publishing.json", bundle.publishing)
    else:
        failure = build_failure_bundle(task, runs)
        _atomic_write_json(target / "task.json", failure.to_task_json())
        _atomic_write_text(target / "error.md", failure.to_error_markdown())

    if task.source.pack_content:
        _atomic_write_text(target / "source-pack.md", task.source.pack_content)

    return target


def _atomic_write_json(path: Path, data: Any) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    tmp.replace(path)
