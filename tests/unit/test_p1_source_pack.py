from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.models import (
    PhaseId,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
)
from llmx_advocate.core.phases.p1_source_pack import P1SourcePack
from llmx_advocate.core.source_pack_loader import InvalidSourcePackError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "example-pack"


def _ctx(source: SourceInput) -> TaskContext:
    task = Task(
        id="01HX",
        title="t",
        source=source,
        config=TaskConfig(),
        current_phase=PhaseId.P1,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(task=task, upstream_outputs={})


@pytest.mark.asyncio
async def test_p1_loads_manual_pack_via_path():
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_path=str(FIXTURES / "manual-pack-example.md")))

    output = await p1.run(ctx)

    assert output["schema_version"] == "1.0"
    assert output["created_by"] == "manual"
    assert output["scout_analysis"] is None
    assert "RAG is dead" in output["body_markdown"]


@pytest.mark.asyncio
async def test_p1_loads_scout_pack_with_judgment_seed():
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_path=str(FIXTURES / "scout-pack-example.md")))

    output = await p1.run(ctx)

    assert output["scout_analysis"]["judgment_seed"]
    assert output["scout_analysis"]["llm_score"] == 8.5


@pytest.mark.asyncio
async def test_p1_loads_pack_via_content():
    pack_text = (FIXTURES / "manual-pack-example.md").read_text(encoding="utf-8")
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_content=pack_text))

    output = await p1.run(ctx)

    assert output["pack_id"] == "manual-2026-04-26-rag-vs-agent"


@pytest.mark.asyncio
async def test_p1_run_fails_when_no_pack_input():
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput())

    with pytest.raises(InvalidSourcePackError, match="must set either"):
        await p1.run(ctx)


@pytest.mark.asyncio
async def test_p1_run_fails_on_invalid_schema():
    bad_pack = "---\nschema_version: '1.0'\npack_id: 'x'\n---\nbody"
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_content=bad_pack))

    with pytest.raises(InvalidSourcePackError, match="schema validation"):
        await p1.run(ctx)


@pytest.mark.asyncio
async def test_p1_qa_passes_for_real_fixture():
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_path=str(FIXTURES / "manual-pack-example.md")))
    output = await p1.run(ctx)

    qa = await p1.qa(output, ctx)

    assert qa.passed_overall is True
    assert all(g.passed for g in qa.gates)


@pytest.mark.asyncio
async def test_p1_qa_fails_on_too_short_body():
    pack_text = """---
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

short.
"""
    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_content=pack_text))
    output = await p1.run(ctx)

    qa = await p1.qa(output, ctx)

    assert qa.passed_overall is False
    failed_ids = {g.gate_id for g in qa.gates if not g.passed}
    assert "P1_body_min_length" in failed_ids


@pytest.mark.asyncio
async def test_p1_qa_fails_when_no_markdown_header():
    pack_text = """---
schema_version: "1.0"
pack_id: "noheader"
created_at: "2026-04-26T00:00:00Z"
created_by: "manual"
source:
  platform: "manual"
  primary_url: "https://example.com"
  title: "no header"
---

This pack body has no markdown headers.
Just plain text long enough to pass the min-length gate by quite a lot of characters being repeated. """ + ("more text. " * 30)

    p1 = P1SourcePack()
    ctx = _ctx(SourceInput(pack_content=pack_text))
    output = await p1.run(ctx)

    qa = await p1.qa(output, ctx)

    failed_ids = {g.gate_id for g in qa.gates if not g.passed}
    assert "P1_has_section_header" in failed_ids
