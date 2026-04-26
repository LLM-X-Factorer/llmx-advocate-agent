from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.llm.provider import LLMResponse
from llmx_advocate.core.models import (
    Angle,
    CharacteristicScores,
    CoreInfo,
    DeepThinking,
    ExportFormat,
    Finding,
    Judgment,
    LayerProfile,
    OpeningStyle,
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
    VideoJSON,
)
from llmx_advocate.core.phases.p4_video_json import (
    P4VideoJSON,
    _common_red_line_rule_gates,
    _gate_jf_judgment_before_intro,
    _gate_jf_judgment_within_15s,
    _gate_opening_structure,
    _gate_per_scene_duration,
    _gate_scene_count,
    _gate_total_duration,
    _resolve_opening_style,
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


def _mk_video(scenes: list[dict] | None = None) -> VideoJSON:
    if scenes is None:
        scenes = _good_scenes()
    return VideoJSON(export_formats=[ExportFormat.LANDSCAPE], scenes=scenes)


def _scene_with_formula_duration(scene_type: str, tts: str, **fields) -> dict:
    """Build a scene whose duration_seconds matches the formula on tts."""
    from llmx_advocate.core.qa.rules import expected_duration
    return {
        "scene_type": scene_type,
        "tts_text": tts,
        "duration_seconds": round(expected_duration(tts), 1),
        **fields,
    }


def _good_scenes() -> list[dict]:
    """A minimal valid 24-scene structure for 留存 tier (~600s)."""
    judgment_essence_chars = "范式从静态到动态"

    scenes: list[dict] = [
        {"scene_type": "cover", "title": "测试封面", "duration_seconds": 3},
        _scene_with_formula_duration(
            "hook",
            f"很多人觉得 RAG 死了，但其实 {judgment_essence_chars}，从一次性召回转向迭代探索。这一点很多人都没注意。",
            main_text=f"很多人觉得 RAG 死了，但其实 {judgment_essence_chars}。",
        ),
        _scene_with_formula_duration(
            "channel_intro",
            "大家好，这里是LLM-X-Factors，一个专注于拆解大语言模型时代底层逻辑的频道。",
            main_text="LLM-X-Factors",
        ),
        _scene_with_formula_duration(
            "hook_support",
            "我们来看一下数据。某项基准 55%，另外能力 1.3 月翻倍，规模化扫描成本降到 1.22 美元。"
            "这些数字告诉我们一件事：从复现到发现，再到规模化扫描成为可能。",
            title="数据支撑",
        ),
    ]
    # Fill to 24 scenes with content + chapter_transitions.
    long_content_tts = (
        "这一段我们讲核心发现。数据支撑这个观点的具体含义是什么？"
        "我们从三个角度来看：第一个是数据本身的规模；第二个是其反映的趋势；"
        "第三个是它对从业者的现实启示。每一点都值得展开来讲。"
    )
    for i in range(19):
        if i % 5 == 0:
            scenes.append(
                _scene_with_formula_duration(
                    "chapter_transition",
                    "我们继续看下一段。",
                    chapter_number=f"{i // 5 + 1:02d}",
                    chapter_title=f"第 {i // 5 + 1} 章",
                )
            )
        else:
            scenes.append(
                _scene_with_formula_duration(
                    "content",
                    long_content_tts,
                    title=f"第 {i} 点",
                    bullets=["要点1", "要点2"],
                )
            )
    scenes.append(
        _scene_with_formula_duration(
            "outro",
            "这里是LLM-X-Factors，我们下期见。",
            headline="我们下期见",
        )
    )
    return scenes


def _ctx(*, opening_style: OpeningStyle = OpeningStyle.JUDGMENT_FIRST, tier: Tier = Tier.LIUCUN) -> TaskContext:
    cfg = TaskConfig(opening_style=opening_style)
    task = Task(
        id="01TEST", title="t",
        source=SourceInput(pack_path="/dummy"),
        config=cfg,
        current_phase=PhaseId.P4,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={
            PhaseId.P1: _mk_pack().model_dump(mode="json"),
            PhaseId.P1_5: Angle(
                hook_source="HN", core_tension="X vs Y",
                your_position="Z", why_readers_care="W",
            ).model_dump(),
            PhaseId.P2: _mk_layer(tier).model_dump(mode="json"),
            PhaseId.P2_5: _mk_judgment().model_dump(),
            PhaseId.P2_6: _mk_deep().model_dump(),
            PhaseId.P3: _mk_info().model_dump(),
        },
    )


# === resolve_opening_style ===


def test_resolve_opening_style_explicit_judgment_first():
    assert _resolve_opening_style(OpeningStyle.JUDGMENT_FIRST, Tier.LIUYIN) == OpeningStyle.JUDGMENT_FIRST


def test_resolve_opening_style_auto_for_liuyin_picks_suspense():
    assert _resolve_opening_style(OpeningStyle.AUTO, Tier.LIUYIN) == OpeningStyle.SUSPENSE_FIRST


def test_resolve_opening_style_auto_for_liucun_picks_judgment():
    assert _resolve_opening_style(OpeningStyle.AUTO, Tier.LIUCUN) == OpeningStyle.JUDGMENT_FIRST


# === Common red line rule gates ===


def test_common_red_lines_pass_on_clean_video():
    gates = _common_red_line_rule_gates(_mk_video())
    assert all(g.passed for g in gates)


def test_red_line_catches_source_backing():
    scenes = _good_scenes()
    scenes[1]["tts_text"] = "今天聊一个 HN 热榜的话题，很有意思。"
    gates = _common_red_line_rule_gates(_mk_video(scenes))
    failed_ids = {g.gate_id for g in gates if not g.passed}
    assert "P4_no_source_backing" in failed_ids


def test_red_line_catches_pan_kol_opening():
    scenes = _good_scenes()
    scenes[1]["tts_text"] = "Hey 各位 B 站朋友们，今天聊..."
    gates = _common_red_line_rule_gates(_mk_video(scenes))
    failed_ids = {g.gate_id for g in gates if not g.passed}
    assert "P4_no_pan_kol_opening" in failed_ids


# === Structural gates ===


def test_scene_count_passes_within_tolerance():
    g = _gate_scene_count(_mk_video(), _mk_layer())
    assert g.passed is True


def test_scene_count_fails_when_too_few():
    short = _good_scenes()[:5]
    g = _gate_scene_count(_mk_video(short), _mk_layer())
    assert g.passed is False


def test_total_duration_passes_within_tolerance():
    g = _gate_total_duration(_mk_video(), _mk_layer())
    assert g.passed is True


def test_per_scene_duration_passes_when_formula_matches():
    g = _gate_per_scene_duration(_mk_video())
    assert g.passed is True


def test_per_scene_duration_fails_on_off_formula():
    scenes = _good_scenes()
    # Scene 3 (hook_support): set duration that's far off the formula.
    scenes[3]["duration_seconds"] = 60  # actual ≈ 11s
    g = _gate_per_scene_duration(_mk_video(scenes))
    assert g.passed is False
    assert g.evidence["off_scenes"]


def test_opening_structure_passes_on_canonical():
    g = _gate_opening_structure(_mk_video())
    assert g.passed is True


def test_opening_structure_fails_when_intro_before_hook():
    scenes = _good_scenes()
    # Swap hook with channel_intro
    scenes[1], scenes[2] = scenes[2], scenes[1]
    g = _gate_opening_structure(_mk_video(scenes))
    assert g.passed is False


# === judgment_first gates ===


def test_jf_judgment_within_15s_passes():
    g = _gate_jf_judgment_within_15s(_mk_video(), _mk_judgment())
    assert g.passed is True


def test_jf_judgment_within_15s_fails_when_essence_buried():
    scenes = _good_scenes()
    # Replace the early scenes' tts so the essence chars don't appear in first 50.
    scenes[1]["tts_text"] = "今天我们要聊一个有趣的话题，看看会发生什么。"
    scenes[2]["tts_text"] = "大家好，欢迎来到这里。"
    scenes[3]["tts_text"] = "我们先看一些数据。"
    g = _gate_jf_judgment_within_15s(_mk_video(scenes), _mk_judgment())
    assert g.passed is False


def test_jf_judgment_before_intro_passes():
    g = _gate_jf_judgment_before_intro(_mk_video())
    assert g.passed is True


def test_jf_judgment_before_intro_fails_when_intro_first():
    scenes = _good_scenes()
    scenes[1], scenes[2] = scenes[2], scenes[1]  # intro now at index 1, hook at 2
    g = _gate_jf_judgment_before_intro(_mk_video(scenes))
    assert g.passed is False


# === run() ===


@pytest.mark.asyncio
async def test_run_invokes_llm_and_returns_video_json(monkeypatch):
    fake_resp = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=2000, output_tokens=2500),
        parsed_json={"export_formats": ["landscape"], "scenes": _good_scenes()},
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p4_video_json.get_provider",
        lambda _: fake_provider,
    )

    output = await P4VideoJSON().run(_ctx())

    assert "scenes" in output
    assert len(output["scenes"]) == 24


# === qa() ===


@pytest.mark.asyncio
async def test_qa_passes_canonical_video(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p4_video_json.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    ctx = _ctx()
    output = _mk_video().model_dump(mode="json")
    qa = await P4VideoJSON().qa(output, ctx)

    assert qa.passed_overall is True
    # 3 rule red lines + 4 structural rule + 3 judge red line + 2 jf style = 12
    gate_ids = {g.gate_id for g in qa.gates}
    assert "P4_no_source_backing" in gate_ids
    assert "P4_judgment_exists" in gate_ids
    assert "P4_jf_judgment_within_15s" in gate_ids


@pytest.mark.asyncio
async def test_qa_fails_when_judge_says_judgment_missing(monkeypatch):
    async def selective_judge(template_ref: str, **kwargs) -> dict:
        if "judgment_exists" in template_ref:
            return {"passed": False, "rationale": "essence not present"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p4_video_json.judge_with_template",
        selective_judge,
    )

    ctx = _ctx()
    output = _mk_video().model_dump(mode="json")
    qa = await P4VideoJSON().qa(output, ctx)

    assert qa.passed_overall is False
    failed_ids = {g.gate_id for g in qa.gates if not g.passed}
    assert "P4_judgment_exists" in failed_ids
