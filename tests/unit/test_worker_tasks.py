"""Worker tests don't need a live Redis. We exercise the core async function
that Celery wraps (`_run_task_async`) directly, plus verify the Celery task
shape is registered and points at it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_celery_task_is_registered():
    from llmx_advocate.worker.app import app
    from llmx_advocate.worker.tasks import run_task

    assert run_task.name == "llmx.run_task"
    assert "llmx.run_task" in app.tasks


@pytest.mark.asyncio
async def test_run_task_async_returns_outcome_dict():
    """Patch the engine entry point so we don't need a live DB for this unit."""
    from llmx_advocate.core.engine import RunOutcome
    from llmx_advocate.core.models import PhaseId, TaskStatus

    fake_outcome = RunOutcome(
        runs_executed=3,
        final_status=TaskStatus.COMPLETED,
        final_phase=PhaseId.P6,
        last_error=None,
    )

    async def fake_runner(session, engine, task_id):
        return fake_outcome

    with (
        patch("llmx_advocate.worker.tasks._run_task_until_blocked", side_effect=fake_runner),
        patch("llmx_advocate.worker.tasks.get_engine") as mock_engine,
    ):
        mock_engine.return_value.dispose = lambda: None  # async-context noop
        # async_sessionmaker on a mock engine — easiest to short-circuit by patching
        # the function that builds it.
        with patch("llmx_advocate.worker.tasks.async_sessionmaker") as mock_factory:
            class _NullSession:
                async def __aenter__(self): return self
                async def __aexit__(self, *a): return None
            mock_factory.return_value = lambda: _NullSession()

            from llmx_advocate.worker.tasks import _run_task_async
            result = await _run_task_async("dummy-task")

    assert result["task_id"] == "dummy-task"
    assert result["final_status"] == "completed"
    assert result["final_phase"] == "P6"
    assert result["runs_executed"] == 3
