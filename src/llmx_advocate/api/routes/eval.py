from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from llmx_advocate.api.deps import db_session
from llmx_advocate.api.routes.tasks import TaskDetail, _enqueue_celery, get_engine
from llmx_advocate.core.engine import run_task_until_blocked
from llmx_advocate.core.evaluation import (
    TaskComparison,
    compare_tasks,
    diff_against_config,
    fork_task,
)
from llmx_advocate.core.models import OpeningStyle, Task
from llmx_advocate.store import repo

router = APIRouter()


class ForkRequest(BaseModel):
    title_suffix: str = "fork"
    llm_model: str | None = None
    llm_provider: str | None = None
    opening_style: OpeningStyle | None = None
    run_immediately: bool = True
    run_async: bool = False


class CompareResponse(BaseModel):
    comparison: TaskComparison
    config_diff: dict


@router.post("/fork/{task_id}", response_model=TaskDetail)
async def fork(
    task_id: str,
    req: ForkRequest,
    session: AsyncSession = Depends(db_session),
) -> TaskDetail:
    try:
        new_task = await fork_task(
            session,
            source_task_id=task_id,
            title_suffix=req.title_suffix,
            llm_model=req.llm_model,
            llm_provider=req.llm_provider,
            opening_style=req.opening_style,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e

    if req.run_immediately:
        if req.run_async and _enqueue_celery(new_task.id):
            runs = await repo.list_phase_runs(session, new_task.id)
            return TaskDetail(task=new_task, runs=runs)
        await run_task_until_blocked(session, get_engine(), new_task.id)

    final = await repo.get_task(session, new_task.id)
    runs = await repo.list_phase_runs(session, new_task.id)
    if final is None:
        raise HTTPException(500, "task disappeared after fork")
    return TaskDetail(task=final, runs=runs)


@router.get("/compare", response_model=CompareResponse)
async def compare(
    a: str,
    b: str,
    session: AsyncSession = Depends(db_session),
) -> CompareResponse:
    try:
        comparison = await compare_tasks(session, a, b)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    config_diff = diff_against_config(comparison.a_config, comparison.b_config)
    return CompareResponse(comparison=comparison, config_diff=config_diff)


class BatchRequest(BaseModel):
    source_pack_path: str | None = None
    source_pack_content: str | None = None
    title: str = "eval batch"
    models: list[str]
    opening_styles: list[OpeningStyle] = [OpeningStyle.AUTO]
    run_async: bool = True


class BatchResponse(BaseModel):
    task_ids: list[str]


@router.post("/batch", response_model=BatchResponse)
async def batch(
    req: BatchRequest,
    session: AsyncSession = Depends(db_session),
) -> BatchResponse:
    if not req.source_pack_path and not req.source_pack_content:
        raise HTTPException(400, "must include source_pack_path or source_pack_content")
    if not req.models:
        raise HTTPException(400, "models list is empty")

    from llmx_advocate.core.models import SourceInput, TaskConfig
    source = SourceInput(
        pack_path=req.source_pack_path,
        pack_content=req.source_pack_content,
    )

    created: list[str] = []
    for model in req.models:
        for style in req.opening_styles:
            cfg = TaskConfig(llm_model=model, opening_style=style)
            task = await repo.create_task(
                session,
                title=f"{req.title} [{model} / {style.value}]",
                source=source,
                config=cfg,
            )
            created.append(task.id)
            if req.run_async and _enqueue_celery(task.id):
                continue
            # Inline fallback
            await run_task_until_blocked(session, get_engine(), task.id)

    return BatchResponse(task_ids=created)


@router.get("/task/{task_id}", response_model=Task)
async def get_eval_task(task_id: str, session: AsyncSession = Depends(db_session)) -> Task:
    """Convenience endpoint used by the CLI to resolve fork outputs."""
    task = await repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} not found")
    return task
