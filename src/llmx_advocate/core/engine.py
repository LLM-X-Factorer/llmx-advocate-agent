from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from llmx_advocate.core.models import (
    DEFAULT_RETRIES,
    PhaseId,
    PhaseRun,
    PhaseRunStatus,
    QAResult,
    Task,
    TaskStatus,
)


@dataclass
class TaskContext:
    task: Task
    upstream_outputs: dict[PhaseId, dict]


class Phase(ABC):
    phase_id: PhaseId
    fallback_target: PhaseId | None = None

    @abstractmethod
    async def run(self, ctx: TaskContext) -> dict:
        """Produce this phase's output. Returns a serialised PhaseOutput dict."""
        raise NotImplementedError

    @abstractmethod
    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        """Run all QA gates against the output."""
        raise NotImplementedError


# Forward-declared phase order. Actual implementations registered by the registry below.
PHASE_ORDER: tuple[PhaseId, ...] = (
    PhaseId.P1,
    PhaseId.P1_5,
    PhaseId.P2,
    PhaseId.P2_5,
    PhaseId.P2_6,
    PhaseId.P3,
    PhaseId.P4,
    PhaseId.P5,
    PhaseId.P6,
)


# Fallback table — written into the engine as per spec §1.3.
FALLBACK_TABLE: dict[PhaseId, PhaseId | None] = {
    PhaseId.P1: None,
    PhaseId.P1_5: PhaseId.P1,
    PhaseId.P2: None,
    PhaseId.P2_5: PhaseId.P1_5,
    PhaseId.P2_6: PhaseId.P2_5,
    PhaseId.P3: PhaseId.P2,  # topic_breadth failure → re-classify tier
    PhaseId.P4: None,
    PhaseId.P5: PhaseId.P4,
    PhaseId.P6: None,
}


class PhaseEngine:
    """Linear state machine with forced-gate retries and write-once fallbacks.

    Concrete behaviour (run a phase, persist outputs, transition) lives in worker.tasks.
    This class is the in-memory contract; persistence is delegated to the store layer.
    """

    def __init__(self, phases: dict[PhaseId, Phase]) -> None:
        self.phases = phases

    def next_phase(self, current: PhaseId) -> PhaseId | None:
        try:
            idx = PHASE_ORDER.index(current)
        except ValueError:
            return None
        return PHASE_ORDER[idx + 1] if idx + 1 < len(PHASE_ORDER) else None

    def fallback_for(self, phase_id: PhaseId) -> PhaseId | None:
        return FALLBACK_TABLE.get(phase_id)

    def decide_transition(self, run: PhaseRun) -> tuple[PhaseId | None, PhaseRunStatus]:
        """Given a finished PhaseRun, decide which phase to schedule next.

        Returns (next_phase_id, terminal_status). next_phase_id=None means task is done
        or stuck waiting for a human (resolved by caller).
        """
        if run.status == PhaseRunStatus.PASSED:
            return self.next_phase(run.phase_id), run.status
        if run.status == PhaseRunStatus.QA_FAILED:
            return run.phase_id, run.status
        if run.status == PhaseRunStatus.QA_FAILED_TERMINAL:
            return self.fallback_for(run.phase_id), run.status
        return run.phase_id, run.status


# === Run-loop helpers ===


@dataclass
class RunOutcome:
    """Summary of a `run_task_until_blocked` invocation."""

    runs_executed: int
    final_status: TaskStatus
    final_phase: PhaseId
    last_error: str | None = None


# Global safety cap: if a task accumulates more than this many phase runs,
# fail it. Otherwise QA-failure-then-fallback loops can spin forever (e.g.
# P2.5 → fallback to P1.5 → P2.5 again with attempt > max_retries).
MAX_TOTAL_PHASE_RUNS = 60


async def _finalize_task(
    session: AsyncSession,
    task_id: str,
    status: TaskStatus,
    final_phase: PhaseId,
    runs_executed: int,
    last_error: str | None = None,
) -> RunOutcome:
    """Set terminal task status, then best-effort persist the export bundle to
    LLMX_OUTPUTS_DIR (if configured). Disk persistence is fire-and-forget — a
    full disk or permission error must not propagate as a task error, since
    the DB record is already authoritative.
    """
    from llmx_advocate.store import repo

    await repo.update_task_status(session, task_id, status=status, current_phase=final_phase)

    if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        await _persist_outputs_best_effort(session, task_id)

    return RunOutcome(runs_executed, status, final_phase, last_error=last_error)


async def _persist_outputs_best_effort(session: AsyncSession, task_id: str) -> None:
    from llmx_advocate.core.export import persist_to_disk
    from llmx_advocate.settings import get_settings
    from llmx_advocate.store import repo

    outputs_dir = get_settings().outputs_dir_path
    if outputs_dir is None:
        return

    try:
        task = await repo.get_task(session, task_id)
        if task is None:
            return
        runs = await repo.list_phase_runs(session, task_id)
        persist_to_disk(task, runs, outputs_dir)
    except Exception as e:
        # Log via stdlib logging so this surfaces in uvicorn / celery output;
        # never re-raise — the export tree is downstream of the task lifecycle.
        import logging
        logging.getLogger(__name__).warning(
            "failed to persist export bundle for task %s: %s", task_id, e
        )


async def run_task_until_blocked(
    session: AsyncSession,
    engine: PhaseEngine,
    task_id: str,
) -> RunOutcome:
    """Drive a task forward until it blocks or completes.

    Blocking conditions:
      - task reaches end of PHASE_ORDER → status=COMPLETED
      - phase QA failed terminally → fallback target queued, then loop continues
      - phase business not implemented (NotImplementedError) → status=PAUSED_FOR_HUMAN
      - generation/runtime error → status=FAILED
      - total phase runs exceeds MAX_TOTAL_PHASE_RUNS → status=FAILED (loop guard)

    On any terminal status (COMPLETED / FAILED), if LLMX_OUTPUTS_DIR is set the
    engine also writes the export bundle to disk (see core/export.py).
    """
    # Imports localised to avoid circular: engine.py is imported by core.phases.* which import models.
    from llmx_advocate.core.phases import build_phase_registry
    from llmx_advocate.store import repo

    if not engine.phases:
        engine = PhaseEngine(phases=build_phase_registry())

    runs_executed = 0
    last_error: str | None = None

    while True:
        task = await repo.get_task(session, task_id)
        if task is None:
            return RunOutcome(runs_executed, TaskStatus.FAILED, PhaseId.P1, last_error="task missing")
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PAUSED_FOR_HUMAN):
            return RunOutcome(runs_executed, task.status, task.current_phase, last_error)

        # Global safety net against fallback-loops.
        all_runs = await repo.list_phase_runs(session, task_id)
        if len(all_runs) >= MAX_TOTAL_PHASE_RUNS:
            return await _finalize_task(
                session, task_id, TaskStatus.FAILED, task.current_phase,
                runs_executed,
                last_error=f"task exceeded {MAX_TOTAL_PHASE_RUNS} total phase runs (loop guard)",
            )

        phase_id = task.current_phase
        phase = engine.phases[phase_id]

        upstream = await _load_upstream_outputs(session, task_id)
        ctx = TaskContext(task=task, upstream_outputs=upstream)

        attempt = await repo.attempt_count(session, task_id, phase_id) + 1
        max_retries = task.config.qa_max_retries.get(phase_id, DEFAULT_RETRIES.get(phase_id, 3))

        started = datetime.now(UTC)
        t0 = time.perf_counter()

        try:
            output = await phase.run(ctx)
        except NotImplementedError as e:
            await _save_run(
                session,
                task_id=task_id,
                phase_id=phase_id,
                attempt=attempt,
                provider=task.config.llm_provider,
                model=task.config.llm_model,
                output={},
                qa=None,
                status=PhaseRunStatus.ERROR,
                started=started,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            await repo.update_task_status(session, task_id, status=TaskStatus.PAUSED_FOR_HUMAN, current_phase=phase_id)
            return RunOutcome(
                runs_executed + 1,
                TaskStatus.PAUSED_FOR_HUMAN,
                phase_id,
                last_error=f"stub phase: {e}",
            )
        except Exception as e:
            import traceback
            last_error = f"{type(e).__name__}: {e}"
            duration_ms = int((time.perf_counter() - t0) * 1000)
            error_output = {
                "_error": last_error,
                "_traceback": traceback.format_exc()[-2000:],
            }

            # Generation-side exceptions (JSON parse / network blips / OpenRouter
            # transient failures) are recoverable — retry within the phase's budget
            # before giving up. Only block-and-fail when retries are exhausted; even
            # then, hand off to fallback if the phase has one (same as qa_failed_terminal).
            if attempt < max_retries:
                await _save_run(
                    session,
                    task_id=task_id,
                    phase_id=phase_id,
                    attempt=attempt,
                    provider=task.config.llm_provider,
                    model=task.config.llm_model,
                    output=error_output,
                    qa=None,
                    status=PhaseRunStatus.ERROR,
                    started=started,
                    duration_ms=duration_ms,
                )
                runs_executed += 1
                continue

            # Retry budget exhausted on a generation exception — same fallback rules
            # as qa_failed_terminal so a transient error doesn't trump the SOP's
            # cycle structure (e.g. P2.5 → P1.5 to try a fresh angle).
            await _save_run(
                session,
                task_id=task_id,
                phase_id=phase_id,
                attempt=attempt,
                provider=task.config.llm_provider,
                model=task.config.llm_model,
                output=error_output,
                qa=None,
                status=PhaseRunStatus.ERROR,
                started=started,
                duration_ms=duration_ms,
            )
            runs_executed += 1
            fallback = engine.fallback_for(phase_id)
            if fallback is None:
                return await _finalize_task(
                    session, task_id, TaskStatus.FAILED, phase_id, runs_executed, last_error=last_error
                )
            await repo.update_task_status(session, task_id, status=TaskStatus.RUNNING, current_phase=fallback)
            continue

        qa: QAResult = await phase.qa(output, ctx)
        duration_ms = int((time.perf_counter() - t0) * 1000)

        if qa.passed_overall:
            await _save_run(
                session,
                task_id=task_id,
                phase_id=phase_id,
                attempt=attempt,
                provider=task.config.llm_provider,
                model=task.config.llm_model,
                output=output,
                qa=qa,
                status=PhaseRunStatus.PASSED,
                started=started,
                duration_ms=duration_ms,
            )
            next_phase = engine.next_phase(phase_id)
            if next_phase is None:
                runs_executed += 1
                return await _finalize_task(
                    session, task_id, TaskStatus.COMPLETED, phase_id, runs_executed, last_error=None
                )
            await repo.update_task_status(session, task_id, status=TaskStatus.RUNNING, current_phase=next_phase)
            runs_executed += 1
            continue

        # QA failed — decide retry vs fallback.
        if attempt < max_retries:
            await _save_run(
                session,
                task_id=task_id,
                phase_id=phase_id,
                attempt=attempt,
                provider=task.config.llm_provider,
                model=task.config.llm_model,
                output=output,
                qa=qa,
                status=PhaseRunStatus.QA_FAILED,
                started=started,
                duration_ms=duration_ms,
            )
            runs_executed += 1
            continue

        # Retry budget exhausted → terminal.
        await _save_run(
            session,
            task_id=task_id,
            phase_id=phase_id,
            attempt=attempt,
            provider=task.config.llm_provider,
            model=task.config.llm_model,
            output=output,
            qa=qa,
            status=PhaseRunStatus.QA_FAILED_TERMINAL,
            started=started,
            duration_ms=duration_ms,
        )
        fallback = engine.fallback_for(phase_id)
        runs_executed += 1
        if fallback is None:
            return await _finalize_task(
                session, task_id, TaskStatus.FAILED, phase_id, runs_executed,
                last_error="qa retries exhausted, no fallback",
            )
        await repo.update_task_status(session, task_id, status=TaskStatus.RUNNING, current_phase=fallback)
        # Loop continues — fallback phase will re-run from scratch.


async def _load_upstream_outputs(session: AsyncSession, task_id: str) -> dict[PhaseId, dict]:
    from llmx_advocate.store import repo

    out: dict[PhaseId, dict] = {}
    runs = await repo.list_phase_runs(session, task_id)
    for run in runs:
        if run.status == PhaseRunStatus.PASSED:
            out[run.phase_id] = run.output  # later passed runs override earlier ones (replay-friendly)
    return out


async def _save_run(
    session: AsyncSession,
    *,
    task_id: str,
    phase_id: PhaseId,
    attempt: int,
    provider: str,
    model: str,
    output: dict,
    qa: QAResult | None,
    status: PhaseRunStatus,
    started: datetime,
    duration_ms: int,
) -> None:
    from llmx_advocate.store import repo

    run = PhaseRun(
        id=repo.new_id(),
        task_id=task_id,
        phase_id=phase_id,
        attempt=attempt,
        llm_provider=provider,
        llm_model=model,
        output=output,
        qa_result=qa,
        status=status,
        started_at=started,
        finished_at=datetime.now(UTC),
        duration_ms=duration_ms,
    )
    await repo.save_phase_run(session, run)
