from pathlib import Path

import pytest

from llmx_advocate.core.engine import PhaseEngine, run_task_until_blocked
from llmx_advocate.core.models import PhaseId, SourceInput, TaskConfig, TaskStatus
from llmx_advocate.core.phases import build_phase_registry
from llmx_advocate.store import repo

FIXTURES = Path(__file__).parent.parent / "fixtures" / "example-pack"


@pytest.fixture
def engine() -> PhaseEngine:
    return PhaseEngine(phases=build_phase_registry())


@pytest.mark.asyncio
async def test_run_task_progresses_through_p2_then_pauses_at_stub(db_session, engine):
    """P1 + P1.5 + P2 all implemented; P2.5 still a stub. Task should pause at P2.5."""
    task = await repo.create_task(
        db_session,
        title="test scout pack",
        source=SourceInput(pack_path=str(FIXTURES / "scout-pack-example.md")),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)

    assert outcome.final_status == TaskStatus.PAUSED_FOR_HUMAN
    assert outcome.final_phase == PhaseId.P2_5

    runs = await repo.list_phase_runs(db_session, task.id)
    by_phase = {r.phase_id: r for r in runs}
    assert by_phase[PhaseId.P1].status.value == "passed"
    assert by_phase[PhaseId.P1_5].status.value == "passed"
    assert by_phase[PhaseId.P2].status.value == "passed"
    assert by_phase[PhaseId.P2_5].status.value == "error"


@pytest.mark.asyncio
async def test_run_task_fails_on_invalid_pack(db_session, engine):
    bad_pack = '---\nschema_version: "1.0"\npack_id: "x"\n---\nbody'
    task = await repo.create_task(
        db_session,
        title="bad pack",
        source=SourceInput(pack_content=bad_pack),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)

    assert outcome.final_status == TaskStatus.FAILED
    assert outcome.last_error is not None
    assert "InvalidSourcePackError" in outcome.last_error


@pytest.mark.asyncio
async def test_run_task_qa_fail_retries_then_terminal(db_session, engine):
    """A pack that loads but fails QA exhausts P1's retry budget (default=3) and fails.

    P1 has no fallback target (None), so terminal QA failure → task FAILED.
    """
    short_pack = """---
schema_version: "1.0"
pack_id: "tiny"
created_at: "2026-04-26T00:00:00Z"
created_by: "manual"
source:
  platform: "manual"
  primary_url: "https://example.com"
  title: "tiny"
---

# title

short body.
"""
    task = await repo.create_task(
        db_session,
        title="qa fail pack",
        source=SourceInput(pack_content=short_pack),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)

    assert outcome.final_status == TaskStatus.FAILED
    runs = await repo.list_phase_runs(db_session, task.id)
    assert all(r.phase_id == PhaseId.P1 for r in runs)
    assert runs[-1].status.value == "qa_failed_terminal"
    assert len(runs) == 3  # default retry budget for P1


@pytest.mark.asyncio
async def test_get_task_and_list(db_session):
    t1 = await repo.create_task(
        db_session,
        title="a",
        source=SourceInput(pack_content="---\nschema_version: '1.0'\npack_id: 'x'\n---\nbody"),
        config=TaskConfig(),
    )
    t2 = await repo.create_task(
        db_session,
        title="b",
        source=SourceInput(pack_path="/nonexistent.md"),
        config=TaskConfig(),
    )

    got = await repo.get_task(db_session, t1.id)
    assert got is not None
    assert got.title == "a"

    listing = await repo.list_tasks(db_session)
    assert {t.id for t in listing} == {t1.id, t2.id}
