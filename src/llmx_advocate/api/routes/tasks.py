from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from llmx_advocate.api.deps import db_session
from llmx_advocate.core.engine import PhaseEngine, run_task_until_blocked
from llmx_advocate.core.models import (
    PhaseId,
    PhaseRun,
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


class TaskDetail(BaseModel):
    task: Task
    runs: list[PhaseRun]


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


@router.put("/{task_id}/phases/{phase}", response_model=PhaseRun)
async def update_phase(task_id: str, phase: PhaseId) -> PhaseRun:
    raise HTTPException(status_code=501, detail="manual edit not implemented yet")


@router.post("/{task_id}/phases/{phase}/qa")
async def rerun_qa(task_id: str, phase: PhaseId) -> dict:
    raise HTTPException(status_code=501, detail="qa rerun not implemented yet")


@router.get("/{task_id}/export")
async def export_task(task_id: str) -> dict:
    raise HTTPException(status_code=501, detail="export not implemented yet")
