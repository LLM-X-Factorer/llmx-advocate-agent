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
    LayerProfile,
    PhaseId,
    SourceInput,
    SourcePack,
    SourcePackSourceMeta,
    Task,
    TaskConfig,
    TaskStatus,
    Tier,
    TokenUsage,
)
from llmx_advocate.core.phases.p2_layer import (
    P2Layer,
    _gate_duration_in_range,
    _gate_export_formats_non_empty,
    _gate_scene_count_in_range,
    _gate_scores_in_bounds,
    _LayerExtractionError,
    _parse_layer_profile,
)


def _ctx(pack: SourcePack, angle: Angle) -> TaskContext:
    task = Task(
        id="01TEST",
        title="t",
        source=SourceInput(pack_path="/dummy"),
        config=TaskConfig(),
        current_phase=PhaseId.P2,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return TaskContext(
        task=task,
        upstream_outputs={
            PhaseId.P1: pack.model_dump(mode="json"),
            PhaseId.P1_5: angle.model_dump(),
        },
    )


def _mk_pack() -> SourcePack:
    return SourcePack(
        schema_version="1.0",
        pack_id="test",
        created_at=datetime.now(UTC),
        created_by="manual",
        source=SourcePackSourceMeta(platform="manual", primary_url="https://e.x", title="t"),
        scout_analysis=None,
        body_markdown="# title\n\n## 评论\n@u: x",
    )


def _mk_angle() -> Angle:
    return Angle(
        hook_source="HN comment",
        core_tension="X vs Y",
        your_position="actually Z",
        why_readers_care="readers ship X",
    )


def _mk_profile(tier: Tier = Tier.LIUCUN, **overrides) -> LayerProfile:
    base = LayerProfile(
        tier=tier,
        characteristic_scores=CharacteristicScores(
            data_impact=4,
            technical_depth=3,
            narrative_quality=4,
            timeliness=5,
            authority=4,
            decision_relevance=5,
        ),
        target_duration_seconds=600,
        target_scene_count=24,
        export_formats=[ExportFormat.LANDSCAPE],
    )
    return base.model_copy(update=overrides)


# === parsing ===


def test_parse_layer_profile_from_dict():
    profile = _parse_layer_profile(
        {
            "tier": "留存",
            "characteristic_scores": {
                "data_impact": 4,
                "technical_depth": 3,
                "narrative_quality": 5,
                "timeliness": 4,
                "authority": 5,
                "decision_relevance": 5,
            },
            "target_duration_seconds": 600,
            "target_scene_count": 24,
            "export_formats": ["landscape"],
        },
        "",
    )
    assert profile.tier == Tier.LIUCUN
    assert profile.target_duration_seconds == 600


def test_parse_layer_profile_raises_on_missing():
    with pytest.raises(_LayerExtractionError):
        _parse_layer_profile({"tier": "引流"}, "")


# === gates ===


def test_duration_gate_pass():
    gate = _gate_duration_in_range(_mk_profile(Tier.LIUCUN, target_duration_seconds=600))
    assert gate.passed is True


def test_duration_gate_fail_too_short():
    gate = _gate_duration_in_range(_mk_profile(Tier.LIUCUN, target_duration_seconds=120))
    assert gate.passed is False


def test_duration_gate_uses_tier_specific_range():
    # 600s is fine for 留存 but well outside 引流 (300-540).
    fails = _gate_duration_in_range(_mk_profile(Tier.LIUYIN, target_duration_seconds=600))
    assert fails.passed is False


def test_scene_gate_pass():
    gate = _gate_scene_count_in_range(_mk_profile(Tier.LIUCUN, target_scene_count=24))
    assert gate.passed is True


def test_scene_gate_fail():
    gate = _gate_scene_count_in_range(_mk_profile(Tier.LIUYIN, target_scene_count=30))
    assert gate.passed is False


def test_export_formats_gate_pass():
    gate = _gate_export_formats_non_empty(_mk_profile())
    assert gate.passed is True


def test_export_formats_gate_fail_when_empty():
    gate = _gate_export_formats_non_empty(_mk_profile(export_formats=[]))
    assert gate.passed is False


def test_scores_gate_pass():
    gate = _gate_scores_in_bounds(_mk_profile())
    assert gate.passed is True


def test_scores_gate_fail_out_of_range():
    profile = _mk_profile()
    profile.characteristic_scores.data_impact = 7  # out of 1-5
    gate = _gate_scores_in_bounds(profile)
    assert gate.passed is False


# === run() ===


@pytest.mark.asyncio
async def test_run_invokes_llm_and_returns_profile(monkeypatch):
    fake_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=200, output_tokens=80),
        parsed_json={
            "tier": "留存",
            "characteristic_scores": {
                "data_impact": 4,
                "technical_depth": 3,
                "narrative_quality": 4,
                "timeliness": 5,
                "authority": 5,
                "decision_relevance": 5,
            },
            "target_duration_seconds": 600,
            "target_scene_count": 24,
            "export_formats": ["landscape"],
        },
    )
    fake_provider = AsyncMock()
    fake_provider.complete = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_layer.get_provider",
        lambda _: fake_provider,
    )

    ctx = _ctx(_mk_pack(), _mk_angle())
    output = await P2Layer().run(ctx)

    assert output["tier"] == "留存"
    assert output["target_duration_seconds"] == 600


@pytest.mark.asyncio
async def test_qa_combines_all_gates():
    p2 = P2Layer()
    ctx = _ctx(_mk_pack(), _mk_angle())
    output = _mk_profile().model_dump(mode="json")

    qa = await p2.qa(output, ctx)

    assert qa.passed_overall is True
    gate_ids = {g.gate_id for g in qa.gates}
    assert "P2_duration_matches_tier" in gate_ids
    assert "P2_scene_count_matches_tier" in gate_ids
    assert "P2_export_formats_set" in gate_ids
    assert "P2_scores_in_1_to_5" in gate_ids


@pytest.mark.asyncio
async def test_qa_fails_when_duration_off():
    p2 = P2Layer()
    ctx = _ctx(_mk_pack(), _mk_angle())
    output = _mk_profile(Tier.LIUYIN, target_duration_seconds=900).model_dump(mode="json")

    qa = await p2.qa(output, ctx)

    assert qa.passed_overall is False
    failed = next(g for g in qa.gates if not g.passed)
    assert failed.gate_id == "P2_duration_matches_tier"
