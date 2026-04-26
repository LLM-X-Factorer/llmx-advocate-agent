from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.llm.provider import LLMResponse
from llmx_advocate.core.models import (
    PhaseId,
    SourceInput,
    SourcePack,
    SourcePackSourceMeta,
    Task,
    TaskConfig,
    TaskStatus,
    TokenUsage,
)
from llmx_advocate.core.phases.p1_5_angle import (
    P1_5Angle,
    _AngleExtractionError,
    _extract_first_json_object,
    _gate_has_community_signal,
    _parse_angle,
)


def _ctx_with_pack(pack: SourcePack) -> TaskContext:
    task = Task(
        id="01HXTEST",
        title="t",
        source=SourceInput(pack_path="/dummy"),
        config=TaskConfig(),
        current_phase=PhaseId.P1_5,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(task=task, upstream_outputs={PhaseId.P1: pack.model_dump(mode="json")})


def _pack_with_body(body: str, *, with_scout: bool = False) -> SourcePack:
    return SourcePack(
        schema_version="1.0",
        pack_id="test",
        created_at=datetime.now(UTC),
        created_by="manual",
        source=SourcePackSourceMeta(
            platform="manual",
            primary_url="https://example.com",
            title="test pack",
        ),
        scout_analysis=None,
        body_markdown=body,
    )


# === _extract_first_json_object ===


def test_extract_json_from_fence():
    text = '前后有废话。\n```json\n{"a": 1, "b": "x"}\n```\n后面也有'
    assert _extract_first_json_object(text) == {"a": 1, "b": "x"}


def test_extract_json_from_bare_braces():
    text = 'wrap {"hook_source": "h", "core_tension": "c"} more'
    got = _extract_first_json_object(text)
    assert got == {"hook_source": "h", "core_tension": "c"}


def test_extract_json_returns_none_when_no_json():
    assert _extract_first_json_object("just words no braces") is None


# === _parse_angle ===


def test_parse_angle_from_dict():
    angle = _parse_angle(
        {
            "hook_source": "HN comment",
            "core_tension": "X vs Y",
            "your_position": "actually Z",
            "why_readers_care": "because they ship X",
        },
        "",
    )
    assert angle.your_position == "actually Z"


def test_parse_angle_raises_when_missing_field():
    with pytest.raises(_AngleExtractionError):
        _parse_angle({"hook_source": "h"}, "")


def test_parse_angle_recovers_from_text_with_fence():
    raw = '```json\n{"hook_source":"a","core_tension":"b","your_position":"c","why_readers_care":"d"}\n```'
    angle = _parse_angle(None, raw)
    assert angle.hook_source == "a"


# === Gate: has_community_signal ===


def test_gate_passes_with_evaluation_section():
    pack = _pack_with_body(
        "# title\n\n## 原文正文\n...\n\n## 评论区精华\n@user1: this is great\n",
    )
    gate = _gate_has_community_signal(pack)
    assert gate.passed is True


def test_gate_fails_when_no_community_section_and_no_scout():
    pack = _pack_with_body("# title\n\n## 原文正文\nplain body, no signal.\n")
    gate = _gate_has_community_signal(pack)
    assert gate.passed is False


# === run() with mocked LLM ===


@pytest.mark.asyncio
async def test_run_invokes_provider_and_returns_angle(monkeypatch):
    fake_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        parsed_json={
            "hook_source": "HN top comment",
            "core_tension": "RAG dead vs not dead",
            "your_position": "the real shift is iterative retrieval",
            "why_readers_care": "anyone shipping retrieval is affected",
        },
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p1_5_angle.get_provider",
        lambda _: fake_provider,
    )

    pack = _pack_with_body("# title\n\n## 评论区精华\n@u1: heated debate\n")
    ctx = _ctx_with_pack(pack)

    output = await P1_5Angle().run(ctx)

    assert output["your_position"] == "the real shift is iterative retrieval"
    fake_provider.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_raises_on_unparseable_response(monkeypatch):
    bad_response = LLMResponse(
        text="I can't help with that",
        usage=TokenUsage(),
        parsed_json=None,
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=bad_response)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p1_5_angle.get_provider",
        lambda _: fake_provider,
    )

    pack = _pack_with_body("# title\n\n## 评论区精华\n@u1: x\n")
    ctx = _ctx_with_pack(pack)

    with pytest.raises(_AngleExtractionError):
        await P1_5Angle().run(ctx)


@pytest.mark.asyncio
async def test_qa_combines_signal_and_judge(monkeypatch):
    """QA returns 2 gates; both must pass for passed_overall."""
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p1_5_angle.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "genuine debate"}),
    )

    pack = _pack_with_body("# title\n\n## 评论区精华\n@u: x\n")
    ctx = _ctx_with_pack(pack)
    output = json.loads(json.dumps({
        "hook_source": "HN",
        "core_tension": "X vs Y",
        "your_position": "Z",
        "why_readers_care": "W",
    }))

    qa = await P1_5Angle().qa(output, ctx)

    assert qa.passed_overall is True
    assert {g.gate_id for g in qa.gates} == {"P1.5_has_community_signal", "P1.5_not_product_announcement"}


@pytest.mark.asyncio
async def test_qa_fails_when_judge_says_product_announcement(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p1_5_angle.judge_with_template",
        AsyncMock(return_value={"passed": False, "rationale": "this reads as a launch frame"}),
    )

    pack = _pack_with_body("# title\n\n## 评论区精华\n@u: x\n")
    ctx = _ctx_with_pack(pack)
    output = {
        "hook_source": "release notes",
        "core_tension": "—",
        "your_position": "Anthropic released X",
        "why_readers_care": "—",
    }

    qa = await P1_5Angle().qa(output, ctx)

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P1.5_not_product_announcement"
