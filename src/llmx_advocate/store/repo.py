"""DAO functions — translate between domain models (Pydantic) and ORM rows.

V0.1 stores all phase outputs inline (in JSON column). MinIO blob storage
(see store/blob.py) is wired for outputs > INLINE_LIMIT but unused until
phases produce large outputs in M3+.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from llmx_advocate.core.models import (
    HumanEdit,
    PhaseId,
    PhaseRun,
    PhaseRunStatus,
    QAResult,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
    TokenUsage,
)
from llmx_advocate.store.db import HumanEditRow, PhaseRunRow, TaskRow


def new_id() -> str:
    return str(ULID())


# === Task ===


def _task_to_row(task: Task) -> TaskRow:
    return TaskRow(
        id=task.id,
        title=task.title,
        source=task.source.model_dump(),
        config=json.loads(task.config.model_dump_json()),
        current_phase=str(task.current_phase),
        status=str(task.status),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _row_to_task(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        title=row.title,
        source=SourceInput.model_validate(row.source),
        config=TaskConfig.model_validate(row.config),
        current_phase=PhaseId(row.current_phase),
        status=TaskStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_task(session: AsyncSession, *, title: str, source: SourceInput, config: TaskConfig) -> Task:
    now = datetime.now(UTC)
    task = Task(
        id=new_id(),
        title=title,
        source=source,
        config=config,
        current_phase=PhaseId.P1,
        status=TaskStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )
    session.add(_task_to_row(task))
    await session.commit()
    return task


async def get_task(session: AsyncSession, task_id: str) -> Task | None:
    row = await session.get(TaskRow, task_id)
    return _row_to_task(row) if row else None


async def list_tasks(session: AsyncSession, *, status: TaskStatus | None = None, limit: int = 50) -> list[Task]:
    stmt = select(TaskRow).order_by(TaskRow.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(TaskRow.status == str(status))
    result = await session.execute(stmt)
    return [_row_to_task(r) for r in result.scalars()]


async def update_task_status(
    session: AsyncSession,
    task_id: str,
    *,
    status: TaskStatus,
    current_phase: PhaseId | None = None,
) -> None:
    row = await session.get(TaskRow, task_id)
    if row is None:
        raise ValueError(f"task {task_id} not found")
    row.status = str(status)
    if current_phase is not None:
        row.current_phase = str(current_phase)
    row.updated_at = datetime.now(UTC)
    await session.commit()


# === PhaseRun ===


def _run_to_row(run: PhaseRun) -> PhaseRunRow:
    return PhaseRunRow(
        id=run.id,
        task_id=run.task_id,
        phase_id=str(run.phase_id),
        attempt=run.attempt,
        trigger=run.trigger,
        llm_provider=run.llm_provider,
        llm_model=run.llm_model,
        output_blob_key=None,
        output_inline=run.output,
        qa_result=run.qa_result.model_dump() if run.qa_result else None,
        status=str(run.status),
        edited_by_human=run.edited_by_human,
        edit_note=run.edit_note,
        cost=run.cost.model_dump(),
        duration_ms=run.duration_ms,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _row_to_run(row: PhaseRunRow) -> PhaseRun:
    return PhaseRun(
        id=row.id,
        task_id=row.task_id,
        phase_id=PhaseId(row.phase_id),
        attempt=row.attempt,
        trigger=row.trigger,  # type: ignore[arg-type]
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        output=row.output_inline or {},
        qa_result=QAResult.model_validate(row.qa_result) if row.qa_result else None,
        status=PhaseRunStatus(row.status),
        edited_by_human=row.edited_by_human,
        edit_note=row.edit_note,
        cost=TokenUsage.model_validate(row.cost) if row.cost else TokenUsage(),
        duration_ms=row.duration_ms,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


async def save_phase_run(session: AsyncSession, run: PhaseRun) -> None:
    session.add(_run_to_row(run))
    await session.commit()


async def list_phase_runs(session: AsyncSession, task_id: str) -> list[PhaseRun]:
    stmt = select(PhaseRunRow).where(PhaseRunRow.task_id == task_id).order_by(PhaseRunRow.started_at.asc())
    result = await session.execute(stmt)
    return [_row_to_run(r) for r in result.scalars()]


async def latest_passed_run(session: AsyncSession, task_id: str, phase_id: PhaseId) -> PhaseRun | None:
    stmt = (
        select(PhaseRunRow)
        .where(
            PhaseRunRow.task_id == task_id,
            PhaseRunRow.phase_id == str(phase_id),
            PhaseRunRow.status == str(PhaseRunStatus.PASSED),
        )
        .order_by(PhaseRunRow.finished_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _row_to_run(row) if row else None


async def attempt_count(session: AsyncSession, task_id: str, phase_id: PhaseId) -> int:
    stmt = select(PhaseRunRow).where(
        PhaseRunRow.task_id == task_id,
        PhaseRunRow.phase_id == str(phase_id),
    )
    result = await session.execute(stmt)
    return len(result.scalars().all())


# === HumanEdit ===


async def save_human_edit(session: AsyncSession, edit: HumanEdit) -> None:
    row = HumanEditRow(
        id=edit.id,
        task_id=edit.task_id,
        phase_id=str(edit.phase_id),
        before=edit.before,
        after=edit.after,
        reason=edit.reason,
        edited_at=edit.edited_at,
    )
    session.add(row)
    await session.commit()


# === Helpers used by tests / engine ===


def serialise_for_db(value: Any) -> Any:
    """JSON-roundtrip a Pydantic-derived dict so SQLAlchemy's JSON column accepts it."""
    return json.loads(json.dumps(value, default=str))
