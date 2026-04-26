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
async def test_p3_topic_breadth_failure_falls_back_to_p2(db_session, engine, monkeypatch):
    """When P3_topic_breadth fails terminally, the engine falls back to P2,
    P2 sees its prior tier in upstream_outputs, switches tier, and the task
    progresses past P3 without an infinite loop.
    """
    from unittest.mock import AsyncMock

    from llmx_advocate.core.llm.provider import LLMResponse
    from llmx_advocate.core.models import TokenUsage

    # Stateful counter so P2 picks a different tier on each invocation.
    p2_call_count = {"n": 0}

    def p2_response_for_call() -> LLMResponse:
        p2_call_count["n"] += 1
        # First call → 留存, second call (after fallback) → 转化.
        tier = "留存" if p2_call_count["n"] == 1 else "转化"
        scene_count = 24 if tier == "留存" else 27
        duration = 600 if tier == "留存" else 720
        return LLMResponse(
            text="",
            usage=TokenUsage(input_tokens=200, output_tokens=80),
            parsed_json={
                "tier": tier,
                "characteristic_scores": {
                    "data_impact": 4, "technical_depth": 4, "narrative_quality": 3,
                    "timeliness": 4, "authority": 4, "decision_relevance": 5,
                },
                "target_duration_seconds": duration,
                "target_scene_count": scene_count,
                "export_formats": ["landscape"],
            },
        )

    layer_provider = AsyncMock()
    layer_provider.complete = AsyncMock(side_effect=lambda req: p2_response_for_call())
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_layer.get_provider",
        lambda _: layer_provider,
    )

    # P3_topic_breadth judge fails when tier=留存, passes when tier=转化.
    async def selective_judge(template_ref: str, **kwargs) -> dict:
        if "topic_breadth" in template_ref:
            tier = kwargs.get("tier", "")
            if tier == "留存":
                return {"passed": False, "rationale": "audience too narrow for 留存"}
            return {"passed": True, "rationale": "ok for narrow tier"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p3_extract.judge_with_template",
        selective_judge,
    )

    task = await repo.create_task(
        db_session,
        title="topic breadth fallback test",
        source=SourceInput(pack_path=str(FIXTURES / "scout-pack-example.md")),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)

    # The pipeline should complete — P3 falls back, P2 picks 转化, P3 passes.
    assert outcome.final_status == TaskStatus.COMPLETED, f"got {outcome.final_status}, error={outcome.last_error}"

    runs = await repo.list_phase_runs(db_session, task.id)
    p2_runs = [r for r in runs if r.phase_id == PhaseId.P2]
    p3_runs = [r for r in runs if r.phase_id == PhaseId.P3]

    # P2 ran twice (initial + after fallback).
    assert len(p2_runs) == 2
    # First passed (留存), second passed (转化)
    assert all(r.status.value == "passed" for r in p2_runs)
    # P3 had at least one terminal failure before final pass.
    assert any(r.status.value == "qa_failed_terminal" for r in p3_runs)
    assert p3_runs[-1].status.value == "passed"


@pytest.mark.asyncio
async def test_run_task_completes_full_pipeline(db_session, engine):
    """All 9 phases (P1..P6) implemented — task should reach COMPLETED end-to-end."""
    task = await repo.create_task(
        db_session,
        title="test scout pack",
        source=SourceInput(pack_path=str(FIXTURES / "scout-pack-example.md")),
        config=TaskConfig(),
    )

    outcome = await run_task_until_blocked(db_session, engine, task.id)

    assert outcome.final_status == TaskStatus.COMPLETED
    assert outcome.final_phase == PhaseId.P6

    runs = await repo.list_phase_runs(db_session, task.id)
    by_phase = {r.phase_id: r for r in runs}
    for pid in (PhaseId.P1, PhaseId.P1_5, PhaseId.P2, PhaseId.P2_5,
                PhaseId.P2_6, PhaseId.P3, PhaseId.P4, PhaseId.P5, PhaseId.P6):
        assert by_phase[pid].status.value == "passed", f"{pid} should pass"


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
