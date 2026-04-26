"""Celery tasks for phase execution.

V0.1 stubs — wire engine + persistence here in next iteration.
"""

from llmx_advocate.worker.app import app


@app.task(name="llmx.run_phase")
def run_phase(task_id: str, phase_id: str) -> dict:
    return {"task_id": task_id, "phase_id": phase_id, "status": "stub"}


@app.task(name="llmx.run_task")
def run_task_until_blocked(task_id: str) -> dict:
    return {"task_id": task_id, "status": "stub"}
