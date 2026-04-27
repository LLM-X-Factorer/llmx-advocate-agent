"""Integration tests: terminal-status tasks trigger export bundle persistence.

Confirms the engine's _finalize_task → persist_to_disk hook path under both
COMPLETED and FAILED outcomes. Uses the same mock_llm fixture from
conftest.py so the full pipeline runs without hitting real LLMs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmx_advocate.core.engine import PhaseEngine, run_task_until_blocked
from llmx_advocate.core.models import SourceInput, TaskConfig, TaskStatus
from llmx_advocate.core.phases import build_phase_registry
from llmx_advocate.store import repo

FIXTURES = Path(__file__).parent.parent / "fixtures" / "example-pack"


@pytest.fixture
def engine() -> PhaseEngine:
    return PhaseEngine(phases=build_phase_registry())


@pytest.fixture
def outputs_dir(tmp_path, monkeypatch):
    """Point LLMX_OUTPUTS_DIR at a tmp path and bust the settings cache.

    Without cache_clear() a previously-cached Settings instance with the env
    unset would silently win, causing tests to pass on tooling but fail in
    production-like config.
    """
    from llmx_advocate import settings as settings_module

    out = tmp_path / "outputs"
    monkeypatch.setenv("LLMX_OUTPUTS_DIR", str(out))
    settings_module.get_settings.cache_clear()
    yield out
    settings_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_completed_task_writes_export_bundle(db_session, engine, outputs_dir):
    task = await repo.create_task(
        db_session,
        title="export bundle smoke",
        source=SourceInput(pack_path=str(FIXTURES / "scout-pack-example.md")),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)
    assert outcome.final_status == TaskStatus.COMPLETED

    # Files should land under outputs_dir/<YYYY-MM-DD>/<task-id>/
    date_dirs = [d for d in outputs_dir.iterdir() if d.is_dir() and d.name != "failures"]
    assert len(date_dirs) == 1
    task_dir = date_dirs[0] / task.id
    assert task_dir.exists()

    assert (task_dir / "task.json").exists()
    assert (task_dir / "summary.md").exists()
    assert (task_dir / "video.json").exists()
    assert (task_dir / "publishing.json").exists()

    meta = json.loads((task_dir / "task.json").read_text())
    assert meta["task_id"] == task.id
    assert meta["status"] == "completed"
    # P1 should have produced a SourcePack with pack_id (from the example fixture)
    assert meta["source_pack_id"] is not None


@pytest.mark.asyncio
async def test_failed_task_writes_failure_bundle(db_session, engine, outputs_dir):
    """A pack with bad schema fails P1 immediately → FAILED → failures/ subtree."""
    bad_pack = '---\nschema_version: "1.0"\npack_id: "test-fail"\n---\nbody'
    task = await repo.create_task(
        db_session,
        title="failure bundle smoke",
        source=SourceInput(pack_content=bad_pack),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)
    assert outcome.final_status == TaskStatus.FAILED

    failures_root = outputs_dir / "failures"
    assert failures_root.exists()

    date_dirs = [d for d in failures_root.iterdir() if d.is_dir()]
    assert len(date_dirs) == 1
    task_dir = date_dirs[0] / task.id
    assert task_dir.exists()

    assert (task_dir / "task.json").exists()
    assert (task_dir / "error.md").exists()

    err_md = (task_dir / "error.md").read_text()
    assert "Failure:" in err_md
    # The error message should mention the schema validation issue
    assert "InvalidSourcePackError" in err_md or "schema validation" in err_md

    # source-pack.md is written when pack_content is provided
    assert (task_dir / "source-pack.md").exists()


@pytest.mark.asyncio
async def test_persistence_disabled_when_env_unset(db_session, engine, tmp_path, monkeypatch):
    """Backwards compat: without LLMX_OUTPUTS_DIR, no files are written."""
    from llmx_advocate import settings as settings_module

    monkeypatch.delenv("LLMX_OUTPUTS_DIR", raising=False)
    settings_module.get_settings.cache_clear()
    try:
        task = await repo.create_task(
            db_session,
            title="no persistence",
            source=SourceInput(pack_path=str(FIXTURES / "scout-pack-example.md")),
            config=TaskConfig(),
        )

        outcome = await run_task_until_blocked(db_session, engine, task.id)
        assert outcome.final_status == TaskStatus.COMPLETED

        # tmp_path should remain empty — engine never wrote anything because
        # LLMX_OUTPUTS_DIR was unset.
        assert list(tmp_path.iterdir()) == []
    finally:
        settings_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_paused_task_does_not_persist(db_session, engine, outputs_dir, monkeypatch):
    """Tasks that pause (e.g. NotImplementedError stub) shouldn't trigger persistence —
    only terminal COMPLETED/FAILED do."""
    # Force P1 to behave like a stub via NotImplementedError → engine pauses.
    from unittest.mock import AsyncMock

    from llmx_advocate.core.phases import p1_source_pack as p1_module

    paused_run = AsyncMock(side_effect=NotImplementedError("P1 is a stub for this test"))
    monkeypatch.setattr(p1_module.P1SourcePack, "run", paused_run, raising=True)

    task = await repo.create_task(
        db_session,
        title="pause smoke",
        source=SourceInput(pack_content="---\nfoo: bar\n---\nbody"),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)
    assert outcome.final_status == TaskStatus.PAUSED_FOR_HUMAN

    # outputs_dir was never created (or was created but empty) — paused != terminal
    assert not outputs_dir.exists() or list(outputs_dir.iterdir()) == []
