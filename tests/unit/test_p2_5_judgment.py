from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.llm.provider import LLMResponse
from llmx_advocate.core.models import (
    Angle,
    CharacteristicScores,
    ExportFormat,
    Judgment,
    LayerProfile,
    PhaseId,
    ScoutAnalysis,
    SourceInput,
    SourcePack,
    SourcePackSourceMeta,
    Task,
    TaskConfig,
    TaskStatus,
    Tier,
    TokenUsage,
)
from llmx_advocate.core.phases.p2_5_judgment import (
    P2_5Judgment,
    _gate_anti_relay_rule,
    _gate_brevity,
    _JudgmentExtractionError,
    _parse_judgment,
)


def _mk_pack(*, with_seed: str | None = None) -> SourcePack:
    scout = (
        ScoutAnalysis(judgment_seed=with_seed) if with_seed else None
    )
    return SourcePack(
        schema_version="1.0",
        pack_id="test",
        created_at=datetime.now(UTC),
        created_by="manual",
        source=SourcePackSourceMeta(platform="manual", primary_url="https://e.x", title="Test"),
        scout_analysis=scout,
        body_markdown="# title\n\n## 评论\n@u: x" * 10,
    )


def _mk_angle() -> Angle:
    return Angle(
        hook_source="HN comment",
        core_tension="X vs Y",
        your_position="actually Z",
        why_readers_care="readers ship X",
    )


def _mk_layer() -> LayerProfile:
    return LayerProfile(
        tier=Tier.LIUCUN,
        characteristic_scores=CharacteristicScores(
            data_impact=4, technical_depth=3, narrative_quality=4,
            timeliness=5, authority=4, decision_relevance=5,
        ),
        target_duration_seconds=600,
        target_scene_count=24,
        export_formats=[ExportFormat.LANDSCAPE],
    )


def _ctx(pack: SourcePack, *, enable_cognition_gap: bool = False) -> TaskContext:
    cfg = TaskConfig(enable_cognition_gap_check=enable_cognition_gap)
    task = Task(
        id="01TEST",
        title="t",
        source=SourceInput(pack_path="/dummy"),
        config=cfg,
        current_phase=PhaseId.P2_5,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={
            PhaseId.P1: pack.model_dump(mode="json"),
            PhaseId.P1_5: _mk_angle().model_dump(),
            PhaseId.P2: _mk_layer().model_dump(mode="json"),
        },
    )


def _mk_judgment(text: str, **overrides) -> Judgment:
    base = Judgment(
        surface="X 被 Y 取代",
        transition="但其实",
        deeper_essence="范式从静态到动态",
        full_sentence=text,
    )
    return base.model_copy(update=overrides)


# === parsing ===


def test_parse_judgment_fills_seed_from_pack():
    """When seed exists and model didn't declare a relation: default to 'accept'."""
    pack = _mk_pack(with_seed="表面 X 但其实 Y")
    parsed_json = {
        "surface": "X",
        "transition": "但其实",
        "deeper_essence": "Y",
        "full_sentence": "X 但其实 Y",
    }
    judgment = _parse_judgment(parsed_json, "", pack)
    assert judgment.seed_judgment == "表面 X 但其实 Y"
    assert judgment.seed_relation == "accept"


def test_parse_judgment_when_model_overrides():
    pack = _mk_pack(with_seed="seed text")
    parsed_json = {
        "surface": "X",
        "transition": "本质上",
        "deeper_essence": "Z",
        "full_sentence": "X 本质上 Z",
        "seed_judgment": "seed text",
        "seed_relation": "override",
        "override_reason": "seed missed Z dimension",
    }
    judgment = _parse_judgment(parsed_json, "", pack)
    assert judgment.seed_relation == "override"
    assert judgment.override_reason == "seed missed Z dimension"


def test_parse_judgment_when_model_deepens():
    """deepen — same topic as seed but more precise angle. The 2026-04-29 trial
    showed that LLM attempt-2 outputs are typically of this kind."""
    pack = _mk_pack(with_seed="推理预算分配比模型架构更能决定小模型实际表现")
    parsed_json = {
        "surface": "4B 小模型基准排名",
        "transition": "实则",
        "deeper_essence": "测试方法本身有偏",
        "full_sentence": "实则测试方法严重偏向不思考的模型，人为制造 Nemotron 的虚假优势",
        "seed_judgment": "推理预算分配比模型架构更能决定小模型实际表现",
        "seed_relation": "deepen",
        "override_reason": "seed only said 'budget > architecture'; we pinpoint the test method bias as the actual mechanism",
    }
    judgment = _parse_judgment(parsed_json, "", pack)
    assert judgment.seed_relation == "deepen"
    assert judgment.override_reason is not None


def test_parse_judgment_when_no_seed():
    pack = _mk_pack(with_seed=None)
    parsed_json = {
        "surface": "X",
        "transition": "其实",
        "deeper_essence": "Y",
        "full_sentence": "X 其实 Y",
    }
    judgment = _parse_judgment(parsed_json, "", pack)
    assert judgment.seed_judgment is None
    assert judgment.seed_relation == "none"


def test_parse_judgment_legacy_overrode_seed_field_migrated():
    """Backwards compat: if a historical PhaseRun output uses the old binary
    overrode_seed field (pre-2026-04-29 format), parse it without crashing."""
    pack = _mk_pack(with_seed="legacy seed")
    parsed_json = {
        "surface": "X",
        "transition": "其实",
        "deeper_essence": "Y",
        "full_sentence": "X 其实 Y",
        "seed_judgment": "legacy seed",
        "overrode_seed": True,
        "override_reason": "legacy",
    }
    judgment = _parse_judgment(parsed_json, "", pack)
    assert judgment.seed_relation == "override"

    parsed_json2 = {
        "surface": "X",
        "transition": "其实",
        "deeper_essence": "Y",
        "full_sentence": "X 其实 Y",
        "seed_judgment": "legacy seed",
        "overrode_seed": False,
    }
    judgment2 = _parse_judgment(parsed_json2, "", pack)
    assert judgment2.seed_relation == "accept"


def test_parse_judgment_raises_on_missing_required_field():
    pack = _mk_pack()
    with pytest.raises(_JudgmentExtractionError):
        _parse_judgment({"surface": "X"}, "", pack)


# === rule gates ===


def test_brevity_passes_under_limit():
    g = _gate_brevity(_mk_judgment("不是因为安全漏洞，而是因为它太好用了——好用到动了巨头的命根子"))
    assert g.passed is True


def test_brevity_fails_over_limit():
    long_text = "这是一个非常非常长的判断" * 10
    g = _gate_brevity(_mk_judgment(long_text))
    assert g.passed is False
    assert g.evidence["cjk_char_count"] > g.evidence["limit"]


def test_anti_relay_rule_catches_source_backing():
    g = _gate_anti_relay_rule(_mk_judgment("今天聊一个 HN 热榜的话题，说说 X 其实是 Y"))
    assert g.passed is False
    assert g.evidence is not None


def test_anti_relay_rule_catches_relay_phrase():
    g = _gate_anti_relay_rule(_mk_judgment("我来给大家解读一下 X 的真正原因"))
    assert g.passed is False


def test_anti_relay_rule_passes_clean():
    g = _gate_anti_relay_rule(_mk_judgment("Alignment 不是技术问题，是权力问题"))
    assert g.passed is True


# === run() ===


@pytest.mark.asyncio
async def test_run_invokes_llm_and_returns_judgment(monkeypatch):
    fake_resp = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=400, output_tokens=120),
        parsed_json={
            "surface": "RAG 被 agent 取代",
            "transition": "但其实",
            "deeper_essence": "检索范式从一次性到迭代",
            "full_sentence": "RAG 没有死，它从主角变成了 agent 的工具",
            "seed_judgment": "表面是 RAG 被 agent 取代，实则是检索范式转移",
            "seed_relation": "override",
            "override_reason": "seed talks about paradigm shift abstractly; my version is concrete",
        },
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.get_provider",
        lambda _: fake_provider,
    )

    ctx = _ctx(_mk_pack(with_seed="表面是 RAG 被 agent 取代，实则是检索范式转移"))
    output = await P2_5Judgment().run(ctx)

    assert output["full_sentence"] == "RAG 没有死，它从主角变成了 agent 的工具"
    assert output["seed_relation"] == "override"


# === qa() ===


@pytest.mark.asyncio
async def test_qa_runs_5_gates_when_brevity_and_relay_pass(monkeypatch):
    """Three judge gates + two rule gates = 5 total when no cognition_gap."""
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx(_mk_pack())
    output = _mk_judgment("不是因为 X，而是因为 Y——动了巨头命根子").model_dump()

    qa = await P2_5Judgment().qa(output, ctx)

    assert qa.passed_overall is True
    assert len(qa.gates) == 5
    expected = {
        "P2.5_brevity",
        "P2.5_anti_relay_rule",
        "P2.5_uniqueness",
        "P2.5_independent_value",
        "P2.5_anti_relay_judge",
    }
    assert {g.gate_id for g in qa.gates} == expected


@pytest.mark.asyncio
async def test_qa_includes_cognition_gap_when_enabled(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx(_mk_pack(), enable_cognition_gap=True)
    output = _mk_judgment("X 但其实 Y").model_dump()

    qa = await P2_5Judgment().qa(output, ctx)

    gate_ids = {g.gate_id for g in qa.gates}
    assert "P2.5_cognition_gap" in gate_ids
    assert len(qa.gates) == 6


@pytest.mark.asyncio
async def test_qa_fails_on_brevity_violation(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    long_text = "这是一个非常非常长的判断" * 10
    ctx = _ctx(_mk_pack())
    output = _mk_judgment(long_text).model_dump()

    qa = await P2_5Judgment().qa(output, ctx)

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P2.5_brevity"


@pytest.mark.asyncio
async def test_qa_fails_on_anti_relay_rule(monkeypatch):
    """When the rule gate already catches a forbidden phrase, judge gates can still pass
    but overall must be False because the rule gate failed."""
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx(_mk_pack())
    output = _mk_judgment("今天聊一个 HN 热榜的话题，X 其实是 Y").model_dump()

    qa = await P2_5Judgment().qa(output, ctx)

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P2.5_anti_relay_rule"


@pytest.mark.asyncio
async def test_qa_fails_when_judge_says_not_unique(monkeypatch):
    """Even with rule gates passing, if uniqueness judge says fail → overall fail."""

    async def fake_judge_with_template(template_ref: str, **kwargs) -> dict:
        if "uniqueness" in template_ref:
            return {"passed": False, "rationale": "this is a paraphrase of the source"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.judge_with_template",
        fake_judge_with_template,
    )

    ctx = _ctx(_mk_pack())
    output = _mk_judgment("X 但其实是 Y").model_dump()

    qa = await P2_5Judgment().qa(output, ctx)

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P2.5_uniqueness"
