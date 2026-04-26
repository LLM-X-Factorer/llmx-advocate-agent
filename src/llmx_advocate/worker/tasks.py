"""Celery tasks for phase execution.

A Celery worker process picks these up off Redis and drives a task forward
in the background. The HTTP API enqueues them; the engine logic itself
lives in core.engine — Celery is just transport.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from llmx_advocate.core.engine import PhaseEngine, run_task_until_blocked as _run_task_until_blocked
from llmx_advocate.core.phases import build_phase_registry
from llmx_advocate.store.db import get_engine
from llmx_advocate.worker.app import app


@app.task(name="llmx.run_task", bind=True, max_retries=0)
def run_task(self, task_id: str) -> dict[str, Any]:  # noqa: ARG001
    """Drive a task until it pauses, completes, or fails.

    Re-enqueueable: callers can fire this whenever they POST /tasks/{id}/actions/run.
    Idempotent — if the task is already in a terminal state the engine no-ops.
    """
    return asyncio.run(_run_task_async(task_id))


async def _run_task_async(task_id: str) -> dict[str, Any]:
    engine_db = get_engine()
    factory = async_sessionmaker(engine_db, expire_on_commit=False)
    phases = build_phase_registry()
    phase_engine = PhaseEngine(phases=phases)

    async with factory() as session:
        outcome = await _run_task_until_blocked(session, phase_engine, task_id)

    return {
        "task_id": task_id,
        "runs_executed": outcome.runs_executed,
        "final_status": outcome.final_status.value,
        "final_phase": outcome.final_phase.value,
        "last_error": outcome.last_error,
    }
