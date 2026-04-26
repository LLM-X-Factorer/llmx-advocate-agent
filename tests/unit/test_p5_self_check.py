from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from llmx_advocate.core.engine import TaskContext
from llmx_advocate.core.models import (
    ExportFormat,
    PhaseId,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
    VideoJSON,
)
from llmx_advocate.core.phases.p5_self_check import (
    P5SelfCheck,
    _gate_has_outro,
    _gate_no_emoji_stack,
    _gate_no_imperative_filler,
    _gate_no_mechanical_enumeration,
    _gate_no_parallel_bold_blocks,
    _gate_per_scene_duration_strict,
    _sync_2_visual_priority,
    _sync_3_card_split,
    _sync_5_duration_cap,
)
from tests.unit.test_p4_video_json import _good_scenes


def _ctx(video: VideoJSON) -> TaskContext:
    task = Task(
        id="01TEST", title="t",
        source=SourceInput(pack_path="/dummy"),
        config=TaskConfig(),
        current_phase=PhaseId.P5,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={PhaseId.P4: video.model_dump(mode="json")},
    )


def _mk_video(scenes: list[dict] | None = None) -> VideoJSON:
    if scenes is None:
        scenes = _good_scenes()
    return VideoJSON(export_formats=[ExportFormat.LANDSCAPE], scenes=scenes)


# === sync rule gates ===


def test_sync_visual_priority_passes_clean():
    g = _sync_2_visual_priority(_mk_video())
    assert g.passed is True


def test_sync_visual_priority_fails_when_pie_chart_with_bullets():
    scenes = _good_scenes()
    scenes[5]["visual"] = {"type": "pie_chart", "data": {"a": 50, "b": 50}}
    scenes[5]["bullets"] = ["要点 1", "要点 2"]
    g = _sync_2_visual_priority(_mk_video(scenes))
    assert g.passed is False
    assert 5 in g.evidence["bad_indices"]


def test_sync_card_split_fails_when_insight_card_with_multi_bullets():
    scenes = _good_scenes()
    scenes[6]["visual"] = {
        "type": "insight_card", "number": 1, "title": "x", "content": "y",
    }
    scenes[6]["bullets"] = ["要点 1", "要点 2", "要点 3"]
    g = _sync_3_card_split(_mk_video(scenes))
    assert g.passed is False


def test_sync_card_split_passes_when_no_single_card():
    g = _sync_3_card_split(_mk_video())
    assert g.passed is True


def test_sync_duration_cap_fails_when_scene_too_long():
    scenes = _good_scenes()
    scenes[5]["duration_seconds"] = 50  # > 40 cap
    g = _sync_5_duration_cap(_mk_video(scenes))
    assert g.passed is False
    assert 5 in g.evidence["bad_indices"]


# === structural ===


def test_has_outro_passes_canonical():
    g = _gate_has_outro(_mk_video())
    assert g.passed is True


def test_has_outro_fails_when_last_is_content():
    scenes = _good_scenes()[:-1]  # drop outro
    g = _gate_has_outro(_mk_video(scenes))
    assert g.passed is False


def test_has_outro_fails_when_signoff_missing():
    scenes = _good_scenes()
    scenes[-1]["tts_text"] = "感谢观看"
    g = _gate_has_outro(_mk_video(scenes))
    assert g.passed is False


def test_per_scene_duration_strict_passes():
    g = _gate_per_scene_duration_strict(_mk_video())
    assert g.passed is True


def test_per_scene_duration_strict_fails_when_off_formula():
    scenes = _good_scenes()
    scenes[3]["duration_seconds"] = 60  # actual ~11s
    g = _gate_per_scene_duration_strict(_mk_video(scenes))
    assert g.passed is False


# === anti-AI smell ===


def test_no_emoji_stack_passes_clean():
    g = _gate_no_emoji_stack(_mk_video())
    assert g.passed is True


def test_no_emoji_stack_fails_with_two_emojis_in_content():
    scenes = _good_scenes()
    scenes[5]["tts_text"] = "这一段我们讲核心发现 🚀。再看 ⭐。"
    g = _gate_no_emoji_stack(_mk_video(scenes))
    assert g.passed is False


def test_no_emoji_stack_excepts_outro():
    scenes = _good_scenes()
    scenes[-1]["tts_text"] = "🎉 这里是LLM-X-Factors，我们下期见。 🎬"
    g = _gate_no_emoji_stack(_mk_video(scenes))
    # outro is in EXCEPT_SCENE_TYPES_FOR_EMOJI → still passes
    assert g.passed is True


def test_no_parallel_bold_blocks_passes_clean():
    g = _gate_no_parallel_bold_blocks(_mk_video())
    assert g.passed is True


def test_no_mechanical_enumeration_fails_when_too_many_groups():
    scenes = _good_scenes()
    # Inject three full "第一/第二/第三" groups across 3 scenes so total markers = 9
    # → groups = 9/3 = 3 (> 2 limit).
    full_group = "第一是 A。第二是 B。第三是 C。"
    for i in range(3):
        scenes[5 + i]["tts_text"] = full_group + scenes[5 + i].get("tts_text", "")
    g = _gate_no_mechanical_enumeration(_mk_video(scenes))
    assert g.passed is False
    assert g.evidence["enum_groups"] >= 3


def test_no_mechanical_enumeration_passes_when_few():
    g = _gate_no_mechanical_enumeration(_mk_video())
    assert g.passed is True


def test_no_imperative_filler_fails_on_match():
    scenes = _good_scenes()
    scenes[5]["tts_text"] = "请你记住这一点很重要。" + scenes[5].get("tts_text", "")
    g = _gate_no_imperative_filler(_mk_video(scenes))
    assert g.passed is False


def test_no_imperative_filler_passes_clean():
    g = _gate_no_imperative_filler(_mk_video())
    assert g.passed is True


# === run() / qa() ===


@pytest.mark.asyncio
async def test_run_returns_validation_report():
    output = await P5SelfCheck().run(_ctx(_mk_video()))
    assert output["syntax_ok"] is True
    assert output["duration_total"] > 0
    assert "cover" in output["scene_type_distribution"]


@pytest.mark.asyncio
async def test_run_records_sync_warnings():
    scenes = _good_scenes()
    scenes[5]["duration_seconds"] = 60  # over cap
    output = await P5SelfCheck().run(_ctx(_mk_video(scenes)))
    assert any("超过硬上限" in w for w in output["sync_warnings"])


@pytest.mark.asyncio
async def test_qa_passes_canonical(monkeypatch):
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p5_self_check.judge_with_template",
        AsyncMock(return_value={"passed": True, "rationale": "ok"}),
    )

    output = await P5SelfCheck().run(_ctx(_mk_video()))
    qa = await P5SelfCheck().qa(output, _ctx(_mk_video()))

    assert qa.passed_overall is True
    expected_gate_ids = {
        "P5_sync_visual_priority",
        "P5_sync_card_split",
        "P5_sync_duration_cap",
        "P5_sync_one_focus",
        "P5_sync_continuity",
        "P5_structure_has_outro",
        "P5_per_scene_duration_strict",
        "P5_no_emoji_stack",
        "P5_no_parallel_bold_blocks",
        "P5_no_mechanical_enumeration",
        "P5_no_imperative_filler",
        "P5_public_verifiable_language",
    }
    assert {g.gate_id for g in qa.gates} == expected_gate_ids


@pytest.mark.asyncio
async def test_qa_fails_when_judge_says_continuity_broken(monkeypatch):
    async def selective_judge(template_ref: str, **kwargs) -> dict:
        if "continuity" in template_ref:
            return {"passed": False, "rationale": "scenes repeat the framing"}
        return {"passed": True, "rationale": "ok"}

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p5_self_check.judge_with_template",
        selective_judge,
    )

    output = await P5SelfCheck().run(_ctx(_mk_video()))
    qa = await P5SelfCheck().qa(output, _ctx(_mk_video()))

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P5_sync_continuity"
