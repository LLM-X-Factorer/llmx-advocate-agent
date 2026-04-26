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
    Publishing,
    SourceInput,
    Story,
    Task,
    TaskConfig,
    TaskStatus,
    Tier,
    TitleOption,
    TokenUsage,
    VideoJSON,
)
from llmx_advocate.core.phases.p6_publishing import (
    P6Publishing,
    _compute_chapter_timestamps,
    _gate_description_format,
    _gate_no_clickbait,
    _gate_pinned_has_timestamps,
    _gate_title_count,
    _gate_title_length,
    _parse_publishing,
    _PublishingExtractionError,
)
from tests.unit.test_p4_video_json import _good_scenes


def _mk_publishing(**overrides) -> Publishing:
    base = Publishing(
        titles=[
            TitleOption(
                text="为什么 90% 的 RAG 项目都活不过 demo？",
                formula_id="liucun_essence",
                rationale="点出 RAG 失败的本质原因",
            ),
            TitleOption(
                text="RAG 没死：检索范式从静态到动态的演进",
                formula_id="liucun_judgment",
                rationale="呈现核心判断",
            ),
        ],
        description="📊 检索范式正在悄悄演进。本期我们拆解 3 个数据信号，"
                    "看为什么 RAG 没有被取代，而是变成 agent 的工具。"
                    "🔍 案例：Anthropic 红队报告里的关键转折。"
                    "💡 洞察：从一次性召回到迭代探索。"
                    "💬 你怎么看？欢迎讨论。",
        pinned_comment=(
            "⏱️ 时间戳：\n"
            "00:00 开场\n"
            "01:30 章节 1：数据现实\n"
            "05:00 章节 2：范式转移\n"
            "08:00 章节 3：对开发者的影响\n"
            "💬 看完有什么想法？"
        ),
    )
    return base.model_copy(update=overrides)


def _mk_judgment() -> Judgment:
    return Judgment(
        surface="RAG 被 agent 取代",
        transition="但其实",
        deeper_essence="检索范式从静态到动态",
        full_sentence="RAG 没有死，它从主角变成了 agent 的工具",
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


def _mk_info() -> CoreInfo:
    return CoreInfo(
        findings=[
            Finding(description="发现1", key_data="55%", source="原文"),
            Finding(description="发现2", key_data="2x", source="原文"),
            Finding(description="发现3", key_data="1.3 月", source="原文"),
        ],
        key_data_points=["数据点1"],
        stories=[Story(title="故事", summary="x")],
        quotable_lines=["金句"],
        authority_anchors=["权威"],
        pain_points=["痛点"],
        advocate_interpretation="解读",
    )


def _mk_deep() -> DeepThinking:
    return DeepThinking(
        why_round=["x"], meaning_round=["y"],
        validation_notes="z", theme="检索范式从静态召回转向迭代探索",
    )


def _mk_video() -> VideoJSON:
    return VideoJSON(export_formats=[ExportFormat.LANDSCAPE], scenes=_good_scenes())


def _ctx(*, tier: Tier = Tier.LIUCUN) -> TaskContext:
    task = Task(
        id="01TEST", title="t",
        source=SourceInput(pack_path="/dummy"),
        config=TaskConfig(),
        current_phase=PhaseId.P6,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={
            PhaseId.P2: _mk_layer(tier).model_dump(mode="json"),
            PhaseId.P2_5: _mk_judgment().model_dump(),
            PhaseId.P2_6: _mk_deep().model_dump(),
            PhaseId.P3: _mk_info().model_dump(),
            PhaseId.P4: _mk_video().model_dump(mode="json"),
        },
    )


# === parsing ===


def test_parse_publishing_from_dict():
    p = _parse_publishing(_mk_publishing().model_dump(), "")
    assert len(p.titles) == 2


def test_parse_publishing_raises_on_one_title():
    bad = _mk_publishing().model_dump()
    bad["titles"] = bad["titles"][:1]
    with pytest.raises(_PublishingExtractionError):
        _parse_publishing(bad, "")


# === chapter timestamps ===


def test_chapter_timestamps_extracted_from_video():
    video = _mk_video()
    timestamps = _compute_chapter_timestamps(video)
    assert len(timestamps) >= 1
    for ts in timestamps:
        assert "title" in ts and "timestamp" in ts
        # mm:ss format
        assert len(ts["timestamp"]) == 5
        assert ts["timestamp"][2] == ":"


def test_chapter_timestamps_increase_monotonically():
    video = _mk_video()
    timestamps = _compute_chapter_timestamps(video)
    seconds = [
        int(ts["timestamp"][:2]) * 60 + int(ts["timestamp"][3:])
        for ts in timestamps
    ]
    assert seconds == sorted(seconds)


# === rule gates ===


def test_title_count_passes_with_2():
    g = _gate_title_count(_mk_publishing())
    assert g.passed is True


def test_title_count_fails_with_4():
    p = _mk_publishing()
    p.titles.append(TitleOption(text="x" * 25))
    p.titles.append(TitleOption(text="y" * 25))
    # bypass min_length=2 max_length=3 by direct mutation; use model_construct
    p2 = Publishing.model_construct(
        titles=p.titles, description=p.description, pinned_comment=p.pinned_comment,
    )
    g = _gate_title_count(p2)
    assert g.passed is False


def test_title_length_passes_canonical():
    g = _gate_title_length(_mk_publishing())
    assert g.passed is True


def test_title_length_fails_when_too_short():
    p = _mk_publishing()
    p.titles[0].text = "RAG 没死"  # too short
    g = _gate_title_length(p)
    assert g.passed is False


def test_title_length_fails_when_too_long():
    p = _mk_publishing()
    p.titles[0].text = "这是一个非常非常长的标题" * 5
    g = _gate_title_length(p)
    assert g.passed is False


def test_no_clickbait_passes_canonical():
    g = _gate_no_clickbait(_mk_publishing())
    assert g.passed is True


def test_no_clickbait_fails_on_chenjing():
    p = _mk_publishing()
    p.titles[0].text = "震惊！RAG 系统居然这样设计才能活下来"
    g = _gate_no_clickbait(p)
    assert g.passed is False


def test_description_format_passes_canonical():
    g = _gate_description_format(_mk_publishing())
    assert g.passed is True


def test_description_format_fails_when_no_emoji():
    p = _mk_publishing()
    p.description = "这里是一段简介，没有 emoji 看点。" * 4
    g = _gate_description_format(p)
    assert g.passed is False


def test_description_format_fails_when_too_short():
    p = _mk_publishing()
    p.description = "📊 太短了。"
    g = _gate_description_format(p)
    assert g.passed is False


def test_pinned_has_timestamps_passes_canonical():
    g = _gate_pinned_has_timestamps(_mk_publishing())
    assert g.passed is True


def test_pinned_has_timestamps_fails_with_one_marker():
    p = _mk_publishing()
    p.pinned_comment = "⏱️ 时间戳：\n00:00 开场\n💬 留言"
    g = _gate_pinned_has_timestamps(p)
    assert g.passed is False


# === run ===


@pytest.mark.asyncio
async def test_run_invokes_llm_and_returns_publishing(monkeypatch):
    fake_resp = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=600, output_tokens=400),
        parsed_json=_mk_publishing().model_dump(),
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p6_publishing.get_provider",
        lambda _: fake_provider,
    )

    output = await P6Publishing().run(_ctx())

    assert len(output["titles"]) == 2
    assert "时间戳" in output["pinned_comment"]


# === qa ===


@pytest.mark.asyncio
async def test_qa_passes_canonical(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p6_publishing.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    output = _mk_publishing().model_dump()
    qa = await P6Publishing().qa(output, _ctx())

    assert qa.passed_overall is True
    expected = {
        "P6_title_count",
        "P6_title_length",
        "P6_no_clickbait",
        "P6_description_format",
        "P6_pinned_has_timestamps",
        "P6_title_reflects_judgment",
        "P6_title_matches_tier",
    }
    assert {g.gate_id for g in qa.gates} == expected


@pytest.mark.asyncio
async def test_qa_fails_when_judge_says_no_judgment(monkeypatch):
    async def selective_judge(template_ref: str, **kwargs) -> dict:
        if "reflects_judgment" in template_ref:
            return {"passed": False, "rationale": "titles only state the topic"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p6_publishing.judge_with_template",
        selective_judge,
    )

    output = _mk_publishing().model_dump()
    qa = await P6Publishing().qa(output, _ctx())

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P6_title_reflects_judgment"
