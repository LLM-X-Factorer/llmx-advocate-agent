from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from llmx_advocate.api.deps import db_session
from llmx_advocate.core.engine import PhaseEngine, TaskContext, run_task_until_blocked
from llmx_advocate.core.models import (
    PhaseId,
    PhaseRun,
    PhaseRunStatus,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
)
from llmx_advocate.core.phases import build_phase_registry
from llmx_advocate.store import repo

router = APIRouter()

_engine: PhaseEngine | None = None


def get_engine() -> PhaseEngine:
    global _engine
    if _engine is None:
        _engine = PhaseEngine(phases=build_phase_registry())
    return _engine


class CreateTaskRequest(BaseModel):
    title: str
    source: SourceInput
    config: TaskConfig | None = None
    run_async: bool = False  # if True: enqueue Celery, return immediately with task in RUNNING


class TaskDetail(BaseModel):
    task: Task
    runs: list[PhaseRun]


def _enqueue_celery(task_id: str) -> str | None:
    """Try to enqueue a Celery task; return the celery task id, or None if Celery
    is unavailable / not configured. Sync fallback is up to the caller."""
    try:
        from llmx_advocate.worker.tasks import run_task as celery_run_task
        result = celery_run_task.delay(task_id)
        return result.id
    except Exception:
        return None


@router.post("", response_model=TaskDetail)
async def create_task(req: CreateTaskRequest, session: AsyncSession = Depends(db_session)) -> TaskDetail:
    if not req.source.pack_path and not req.source.pack_content:
        raise HTTPException(400, "source must include pack_path or pack_content")

    task = await repo.create_task(
        session,
        title=req.title,
        source=req.source,
        config=req.config or TaskConfig(),
    )

    if req.run_async and _enqueue_celery(task.id):
        # Hand off to the worker; return the task in RUNNING state immediately.
        runs = await repo.list_phase_runs(session, task.id)
        return TaskDetail(task=task, runs=runs)

    # Default path: drive the task synchronously inline.
    await run_task_until_blocked(session, get_engine(), task.id)

    final_task = await repo.get_task(session, task.id)
    if final_task is None:
        raise HTTPException(500, "task disappeared after creation")
    runs = await repo.list_phase_runs(session, task.id)
    return TaskDetail(task=final_task, runs=runs)


@router.get("", response_model=list[Task])
async def list_tasks(
    status: TaskStatus | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(db_session),
) -> list[Task]:
    return await repo.list_tasks(session, status=status, limit=limit)


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task_detail(task_id: str, session: AsyncSession = Depends(db_session)) -> TaskDetail:
    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")
    runs = await repo.list_phase_runs(session, task_id)
    return TaskDetail(task=task, runs=runs)


@router.post("/{task_id}/actions/run", response_model=TaskDetail)
async def run_action(task_id: str, session: AsyncSession = Depends(db_session)) -> TaskDetail:
    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")
    if task.status == TaskStatus.PAUSED_FOR_HUMAN:
        await repo.update_task_status(
            session, task_id, status=TaskStatus.RUNNING, current_phase=task.current_phase
        )

    await run_task_until_blocked(session, get_engine(), task_id)

    final_task = await repo.get_task(session, task_id)
    runs = await repo.list_phase_runs(session, task_id)
    if final_task is None:
        raise HTTPException(500, "task disappeared during run")
    return TaskDetail(task=final_task, runs=runs)


@router.post("/{task_id}/actions/pause", status_code=status.HTTP_200_OK)
async def pause_action(task_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")
    await repo.update_task_status(
        session, task_id, status=TaskStatus.PAUSED_FOR_HUMAN, current_phase=task.current_phase
    )
    return {"task_id": task_id, "status": "paused_for_human"}


@router.get("/{task_id}/phases/{phase}", response_model=list[PhaseRun])
async def get_phase_runs(
    task_id: str, phase: PhaseId, session: AsyncSession = Depends(db_session)
) -> list[PhaseRun]:
    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")
    all_runs = await repo.list_phase_runs(session, task_id)
    return [r for r in all_runs if r.phase_id == phase]


class UpdatePhaseRequest(BaseModel):
    output: dict
    edit_note: str = ""


@router.put("/{task_id}/phases/{phase}", response_model=PhaseRun)
async def update_phase(
    task_id: str,
    phase: PhaseId,
    req: UpdatePhaseRequest,
    session: AsyncSession = Depends(db_session),
) -> PhaseRun:
    """Manual override for a phase's output.

    Per spec §1: human edits never bypass QA — this saves a new PhaseRun with
    edited_by_human=True flag, then re-runs the gates against the edited output.
    The caller can choose to skip QA only by also calling /qa themselves with
    different content.
    """
    from datetime import UTC, datetime

    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")

    # Run QA on the edited output
    phases = build_phase_registry()
    if phase not in phases:
        raise HTTPException(400, f"unknown phase: {phase}")
    upstream = await _load_upstream_for_qa(session, task_id, phase)
    ctx_task = TaskContext(task=task, upstream_outputs=upstream)
    qa_result = await phases[phase].qa(req.output, ctx_task)

    # Persist as a new PhaseRun marked edited_by_human
    attempt_n = await repo.attempt_count(session, task_id, phase) + 1
    now = datetime.now(UTC)
    run = PhaseRun(
        id=repo.new_id(),
        task_id=task_id,
        phase_id=phase,
        attempt=attempt_n,
        trigger="manual_resume",
        llm_provider=task.config.llm_provider,
        llm_model=task.config.llm_model,
        output=req.output,
        qa_result=qa_result,
        status=PhaseRunStatus.PASSED if qa_result.passed_overall else PhaseRunStatus.QA_FAILED,
        edited_by_human=True,
        edit_note=req.edit_note,
        started_at=now,
        finished_at=now,
        duration_ms=0,
    )
    await repo.save_phase_run(session, run)
    return run


@router.post("/{task_id}/phases/{phase}/qa", response_model=PhaseRun)
async def rerun_qa(
    task_id: str,
    phase: PhaseId,
    session: AsyncSession = Depends(db_session),
) -> PhaseRun:
    """Re-run QA gates against the latest passed output of a phase, without
    re-generating. Useful after schema/judge changes to validate prior outputs."""
    from datetime import UTC, datetime

    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")

    last = await repo.latest_passed_run(session, task_id, phase)
    if last is None:
        raise HTTPException(404, f"phase {phase} has no passed run on task {task_id}")

    phases = build_phase_registry()
    if phase not in phases:
        raise HTTPException(400, f"unknown phase: {phase}")
    upstream = await _load_upstream_for_qa(session, task_id, phase)
    ctx_task = TaskContext(task=task, upstream_outputs=upstream)
    qa_result = await phases[phase].qa(last.output, ctx_task)

    attempt_n = await repo.attempt_count(session, task_id, phase) + 1
    now = datetime.now(UTC)
    run = PhaseRun(
        id=repo.new_id(),
        task_id=task_id,
        phase_id=phase,
        attempt=attempt_n,
        trigger="manual_qa_rerun",
        llm_provider=task.config.llm_provider,
        llm_model=task.config.llm_model,
        output=last.output,
        qa_result=qa_result,
        status=PhaseRunStatus.PASSED if qa_result.passed_overall else PhaseRunStatus.QA_FAILED,
        edited_by_human=False,
        started_at=now,
        finished_at=now,
        duration_ms=0,
    )
    await repo.save_phase_run(session, run)
    return run


async def _load_upstream_for_qa(session: AsyncSession, task_id: str, phase: PhaseId) -> dict:
    """Load passed PhaseRun outputs as upstream context for a single phase rerun."""
    out: dict = {}
    runs = await repo.list_phase_runs(session, task_id)
    for r in runs:
        if r.status == PhaseRunStatus.PASSED:
            out[r.phase_id] = r.output
    return out


class TaskExport(BaseModel):
    task_id: str
    title: str
    status: str
    video_json: dict | None = None
    publishing: dict | None = None
    judgment: str | None = None
    theme: str | None = None
    tier: str | None = None


@router.get("/{task_id}/export", response_model=TaskExport)
async def export_task(task_id: str, session: AsyncSession = Depends(db_session)) -> TaskExport:
    """Bundle the publishable artefacts (Video JSON + titles/description/pinned)
    plus a few headline metadata fields. Works on tasks in any state — exports
    whatever passed phases produced; missing phases come back as null."""
    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")

    runs = await repo.list_phase_runs(session, task_id)
    by_phase: dict[str, dict] = {}
    for r in runs:
        if r.status == PhaseRunStatus.PASSED:
            by_phase[str(r.phase_id)] = r.output

    layer = by_phase.get("P2") or {}
    judgment = by_phase.get("P2.5") or {}
    deep = by_phase.get("P2.6") or {}
    video = by_phase.get("P4")
    publishing = by_phase.get("P6")

    return TaskExport(
        task_id=task.id,
        title=task.title,
        status=task.status.value,
        video_json=video,
        publishing=publishing,
        judgment=judgment.get("full_sentence") if judgment else None,
        theme=deep.get("theme") if deep else None,
        tier=layer.get("tier") if layer else None,
    )
