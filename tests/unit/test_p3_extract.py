from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.llm.provider import LLMResponse
from llmx_advocate.core.models import (
    CharacteristicScores,
    CoreInfo,
    DeepThinking,
    ExportFormat,
    Finding,
    Judgment,
    LayerProfile,
    PhaseId,
    SourceInput,
    SourcePack,
    SourcePackSourceMeta,
    Story,
    Task,
    TaskConfig,
    TaskStatus,
    Tier,
    TokenUsage,
)
from llmx_advocate.core.phases.p3_extract import (
    P3Extract,
    _ExtractionError,
    _gate_findings_count,
    _gate_findings_have_data,
    _gate_material_richness,
    _parse_core_info,
)


def _mk_pack() -> SourcePack:
    return SourcePack(
        schema_version="1.0",
        pack_id="t",
        created_at=datetime.now(UTC),
        created_by="manual",
        source=SourcePackSourceMeta(platform="manual", primary_url="https://e.x", title="t"),
        scout_analysis=None,
        body_markdown="# t\n\n## 评论\n@u: x" * 5,
    )


def _mk_layer(tier: Tier = Tier.LIUCUN) -> LayerProfile:
    return LayerProfile(
        tier=tier,
        characteristic_scores=CharacteristicScores(
            data_impact=4, technical_depth=3, narrative_quality=4,
            timeliness=5, authority=4, decision_relevance=5,
        ),
        target_duration_seconds=600,
        target_scene_count=24,
        export_formats=[ExportFormat.LANDSCAPE],
    )


def _mk_judgment() -> Judgment:
    return Judgment(
        surface="X 被 Y 取代", transition="但其实",
        deeper_essence="范式从静态到动态",
        full_sentence="不是 X 被 Y 取代，而是检索范式从静态到动态",
    )


def _mk_deep() -> DeepThinking:
    return DeepThinking(
        why_round=["x"], meaning_round=["y"],
        validation_notes="z", theme="检索范式从静态召回转向迭代探索",
    )


def _ctx(*, tier: Tier = Tier.LIUCUN) -> TaskContext:
    task = Task(
        id="01TEST", title="t",
        source=SourceInput(pack_path="/dummy"),
        config=TaskConfig(),
        current_phase=PhaseId.P3,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={
            PhaseId.P1: _mk_pack().model_dump(mode="json"),
            PhaseId.P2: _mk_layer(tier).model_dump(mode="json"),
            PhaseId.P2_5: _mk_judgment().model_dump(),
            PhaseId.P2_6: _mk_deep().model_dump(),
        },
    )


def _mk_info(**overrides) -> CoreInfo:
    base = CoreInfo(
        findings=[
            Finding(description="发现1", key_data="55%", source="原文"),
            Finding(description="发现2", key_data="2倍", source="原文"),
            Finding(description="发现3", key_data="1.3 个月翻倍", source="原文"),
        ],
        key_data_points=["460 万美元 — 模拟漏洞总价值"],
        stories=[Story(title="时间差", summary="AI 比人类黑客早四天")],
        quotable_lines=["规模化扫描成为可能"],
        authority_anchors=["Anthropic 报告"],
        pain_points=["开发者忽视 agent 的安全风险"],
        advocate_interpretation="对 AI 从业者来说...",
    )
    return base.model_copy(update=overrides)


# === parsing ===


def test_parse_core_info_from_dict():
    info = _parse_core_info(
        {
            "findings": [
                {"description": "f1", "key_data": "x", "source": "y"},
                {"description": "f2", "key_data": "x", "source": "y"},
                {"description": "f3", "key_data": "x", "source": "y"},
            ],
            "key_data_points": ["d"],
            "stories": [{"title": "s", "summary": "x"}],
            "quotable_lines": ["q"],
            "authority_anchors": ["a"],
            "pain_points": ["p"],
            "advocate_interpretation": "i",
        },
        "",
    )
    assert len(info.findings) == 3


def test_parse_core_info_raises_when_too_few_findings():
    with pytest.raises(_ExtractionError):
        _parse_core_info(
            {
                "findings": [{"description": "only one"}],
                "advocate_interpretation": "x",
            },
            "",
        )


def test_parse_core_info_raises_when_too_many_findings():
    findings = [{"description": f"f{i}"} for i in range(7)]
    with pytest.raises(_ExtractionError):
        _parse_core_info(
            {"findings": findings, "advocate_interpretation": "x"},
            "",
        )


# === gates ===


def test_findings_count_passes_with_3():
    g = _gate_findings_count(_mk_info())
    assert g.passed is True


def test_findings_count_fails_with_2():
    info = _mk_info(findings=[
        Finding(description="f1", key_data="x"),
        Finding(description="f2", key_data="y"),
    ])
    # Need to bypass model validation manually since min_length=3.
    # Use model_construct to skip validation.
    info2 = CoreInfo.model_construct(
        **{**info.model_dump(), "findings": info.findings}
    )
    g = _gate_findings_count(info2)
    assert g.passed is False


def test_findings_have_data_passes_when_all_have_key_data():
    g = _gate_findings_have_data(_mk_info())
    assert g.passed is True


def test_findings_have_data_fails_when_one_missing():
    info = _mk_info(findings=[
        Finding(description="f1", key_data="x"),
        Finding(description="f2", key_data=None, source=None),
        Finding(description="f3", source="x"),
    ])
    g = _gate_findings_have_data(info)
    assert g.passed is False
    assert g.evidence["missing_indices"] == [1]


def test_material_richness_passes_with_all_5():
    g = _gate_material_richness(_mk_info())
    assert g.passed is True
    assert g.evidence["covered_count"] == 5


def test_material_richness_passes_with_3():
    g = _gate_material_richness(_mk_info(
        quotable_lines=[],
        authority_anchors=[],
    ))
    # Still has data + story + pain
    assert g.passed is True
    assert g.evidence["covered_count"] == 3


def test_material_richness_fails_with_2():
    g = _gate_material_richness(_mk_info(
        stories=[],
        quotable_lines=[],
        authority_anchors=[],
    ))
    # Only data + pain_points
    assert g.passed is False
    assert g.evidence["covered_count"] == 2


def test_material_richness_recognises_data_in_findings_when_no_key_data_points():
    info = _mk_info(
        key_data_points=[],
        stories=[],
        quotable_lines=[],
        authority_anchors=[],
        pain_points=[],
    )
    # findings still have key_data → 1/5 (data only)
    g = _gate_material_richness(info)
    assert g.evidence["covered_count"] == 1


# === run ===


@pytest.mark.asyncio
async def test_run_invokes_llm_and_returns_core_info(monkeypatch):
    fake_resp = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=500, output_tokens=400),
        parsed_json={
            "findings": [
                {"description": "发现1", "key_data": "55%", "source": "原文 §3"},
                {"description": "发现2", "key_data": "1.3 个月", "source": "Anthropic"},
                {"description": "发现3", "key_data": "920×", "source": "原文 §5"},
            ],
            "key_data_points": ["460 万美元 — 模拟环境总价值"],
            "stories": [{"title": "四天时间差", "summary": "AI 比人类早四天"}],
            "quotable_lines": ["从复现到发现"],
            "authority_anchors": ["Anthropic 红队报告"],
            "pain_points": ["工程师不理解 agent 安全边界"],
            "advocate_interpretation": "三个信号...",
        },
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p3_extract.get_provider",
        lambda _: fake_provider,
    )

    output = await P3Extract().run(_ctx())

    assert len(output["findings"]) == 3
    assert output["pain_points"] == ["工程师不理解 agent 安全边界"]


# === qa ===


@pytest.mark.asyncio
async def test_qa_skips_topic_breadth_when_tier_is_conversion(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p3_extract.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx(tier=Tier.ZHUANHUA)
    output = _mk_info().model_dump()
    qa = await P3Extract().qa(output, ctx)

    assert qa.passed_overall is True
    gate_ids = {g.gate_id for g in qa.gates}
    assert "P3_topic_breadth" not in gate_ids
    assert len(qa.gates) == 3


@pytest.mark.asyncio
async def test_qa_includes_topic_breadth_for_other_tiers(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p3_extract.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx(tier=Tier.LIUYIN)
    output = _mk_info().model_dump()
    qa = await P3Extract().qa(output, ctx)

    gate_ids = {g.gate_id for g in qa.gates}
    assert "P3_topic_breadth" in gate_ids
    assert len(qa.gates) == 4


@pytest.mark.asyncio
async def test_qa_fails_on_material_richness_short(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p3_extract.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx()
    info = _mk_info(stories=[], quotable_lines=[], authority_anchors=[])
    output = info.model_dump()

    qa = await P3Extract().qa(output, ctx)

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P3_material_richness"
