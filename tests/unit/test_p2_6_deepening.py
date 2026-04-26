from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.llm.provider import LLMResponse
from llmx_advocate.core.models import (
    DeepThinking,
    Judgment,
    PhaseId,
    SourceInput,
    SourcePack,
    SourcePackSourceMeta,
    Task,
    TaskConfig,
    TaskStatus,
    TokenUsage,
)
from llmx_advocate.core.phases.p2_6_deepening import (
    P2_6Deepening,
    _DeepeningExtractionError,
    _gate_beyond_surface_rule,
    _gate_theme_brevity,
    _parse_deep_thinking,
)


def _mk_pack() -> SourcePack:
    return SourcePack(
        schema_version="1.0",
        pack_id="test",
        created_at=datetime.now(UTC),
        created_by="manual",
        source=SourcePackSourceMeta(platform="manual", primary_url="https://e.x", title="Test"),
        scout_analysis=None,
        body_markdown="# title\n\n## 评论\n@u: x" * 5,
    )


def _mk_judgment() -> Judgment:
    return Judgment(
        surface="X 被 Y 取代",
        transition="但其实",
        deeper_essence="范式从静态到动态",
        full_sentence="不是 X 被 Y 取代，而是检索范式从静态到动态",
    )


def _ctx() -> TaskContext:
    cfg = TaskConfig()
    task = Task(
        id="01TEST",
        title="t",
        source=SourceInput(pack_path="/dummy"),
        config=cfg,
        current_phase=PhaseId.P2_6,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={
            PhaseId.P1: _mk_pack().model_dump(mode="json"),
            PhaseId.P2_5: _mk_judgment().model_dump(),
        },
    )


def _mk_deep(theme: str = "范式从静态召回转向迭代探索") -> DeepThinking:
    return DeepThinking(
        why_round=["为什么1：召回模式天然受限于一次匹配", "为什么2：用户问题往往多步"],
        meaning_round=["对工程师：放弃一次召回的执念", "对产品：反馈到生产环境的指标会变"],
        validation_notes="三轮追问后判断仍成立，theme 沿用 P2.5 略加精炼",
        theme=theme,
    )


# === parsing ===


def test_parse_deep_thinking_from_dict():
    deep = _parse_deep_thinking(
        {
            "why_round": ["为什么1：x"],
            "meaning_round": ["意味着1：y"],
            "validation_notes": "z",
            "theme": "判断站住",
        },
        "",
    )
    assert deep.theme == "判断站住"


def test_parse_deep_thinking_raises_on_missing_theme():
    with pytest.raises(_DeepeningExtractionError):
        _parse_deep_thinking(
            {"why_round": [], "meaning_round": [], "validation_notes": "x"},
            "",
        )


# === rule gates ===


def test_brevity_gate_passes():
    g = _gate_theme_brevity(_mk_deep("不是 X 被 Y 取代"))
    assert g.passed is True


def test_brevity_gate_fails_when_too_long():
    g = _gate_theme_brevity(_mk_deep("一" * 60))
    assert g.passed is False


def test_brevity_gate_fails_when_empty():
    g = _gate_theme_brevity(_mk_deep(""))
    assert g.passed is False


def test_beyond_surface_rule_catches_adjective():
    g = _gate_beyond_surface_rule(_mk_deep("RAG 真的很重要"))
    assert g.passed is False
    assert g.evidence["matched"] == "很重要"


def test_beyond_surface_rule_catches_slogan():
    g = _gate_beyond_surface_rule(_mk_deep("Agent 是未来"))
    assert g.passed is False


def test_beyond_surface_rule_passes_concrete():
    g = _gate_beyond_surface_rule(_mk_deep("检索范式从静态召回转向迭代探索"))
    assert g.passed is True


# === run ===


@pytest.mark.asyncio
async def test_run_invokes_llm_and_returns_deep_thinking(monkeypatch):
    fake_resp = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=300, output_tokens=200),
        parsed_json={
            "why_round": ["为什么1：检索是单次匹配的产物", "为什么2：agent 把召回拆成多步"],
            "meaning_round": ["对开发：放弃一次到位执念", "对评测：MTEB 这类静态 benchmark 失真"],
            "validation_notes": "三轮追问后判断仍成立，theme 在原 judgment 上略作精炼",
            "theme": "检索范式从静态召回转向迭代探索",
        },
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_6_deepening.get_provider",
        lambda _: fake_provider,
    )

    output = await P2_6Deepening().run(_ctx())

    assert output["theme"] == "检索范式从静态召回转向迭代探索"
    assert len(output["why_round"]) >= 2


# === qa ===


@pytest.mark.asyncio
async def test_qa_runs_6_gates(monkeypatch):
    """2 rule + 4 judge = 6 gates total."""
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_6_deepening.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    output = _mk_deep().model_dump()
    qa = await P2_6Deepening().qa(output, _ctx())

    assert qa.passed_overall is True
    assert len(qa.gates) == 6
    expected = {
        "P2.6_theme_brevity",
        "P2.6_beyond_surface_rule",
        "P2.6_beyond_surface_judge",
        "P2.6_makes_rethink",
        "P2.6_transferable",
        "P2.6_hook_independent",
    }
    assert {g.gate_id for g in qa.gates} == expected


@pytest.mark.asyncio
async def test_qa_fails_on_surface_adjective(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_6_deepening.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    output = _mk_deep("RAG 真的很重要").model_dump()
    qa = await P2_6Deepening().qa(output, _ctx())

    assert qa.passed_overall is False
    failed_ids = {g.gate_id for g in qa.gates if not g.passed}
    assert "P2.6_beyond_surface_rule" in failed_ids


@pytest.mark.asyncio
async def test_qa_fails_when_judge_says_not_transferable(monkeypatch):
    async def selective_judge(template_ref: str, **kwargs) -> dict:
        if "transferable" in template_ref:
            return {"passed": False, "rationale": "this insight only fits one case"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_6_deepening.judge_with_template",
        selective_judge,
    )

    output = _mk_deep().model_dump()
    qa = await P2_6Deepening().qa(output, _ctx())

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P2.6_transferable"


@pytest.mark.asyncio
async def test_qa_fails_when_hook_dependent(monkeypatch):
    async def selective_judge(template_ref: str, **kwargs) -> dict:
        if "hook_independent" in template_ref:
            return {"passed": False, "rationale": "removing the controversy collapses the theme"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_6_deepening.judge_with_template",
        selective_judge,
    )

    output = _mk_deep().model_dump()
    qa = await P2_6Deepening().qa(output, _ctx())

    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P2.6_hook_independent"
