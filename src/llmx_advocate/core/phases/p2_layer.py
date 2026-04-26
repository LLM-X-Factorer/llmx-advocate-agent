from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import (
    Angle,
    LayerProfile,
    PhaseId,
    QAGate,
    QAResult,
    SourcePack,
    Tier,
)
from llmx_advocate.core.prompts import render

BODY_EXCERPT_MAX_CHARS = 4000

P2_SYSTEM = (
    "You are an analyst classifying source material into a Bilibili content tier "
    "and producing a characteristic profile. Return strict JSON, no commentary."
)


# tier → (duration range, scene count range)
TIER_DURATION_RANGE: dict[Tier, tuple[int, int]] = {
    Tier.LIUYIN: (300, 540),
    Tier.LIUCUN: (450, 780),
    Tier.ZHUANHUA: (570, 960),
}
TIER_SCENE_RANGE: dict[Tier, tuple[int, int]] = {
    Tier.LIUYIN: (14, 19),
    Tier.LIUCUN: (22, 26),
    Tier.ZHUANHUA: (24, 31),
}


class _LayerExtractionError(RuntimeError):
    pass


class P2Layer(Phase):
    """P2 — Content Layer & Characteristic.

    Reads SourcePack + Angle from upstream, returns LayerProfile (tier, 6-dim
    characteristic scores, target duration / scene count / export formats).

    On retry exhaustion → no fallback (P2 has no upstream to retry against).
    """

    phase_id = PhaseId.P2
    fallback_target = None

    async def run(self, ctx: TaskContext) -> dict:
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        angle = Angle.model_validate(ctx.upstream_outputs[PhaseId.P1_5])

        scout_suggested = (
            pack.scout_analysis.suggested_layer
            if pack.scout_analysis and pack.scout_analysis.suggested_layer
            else None
        )

        # If P3 fell back to P2, our previous (passing) P2 output is in upstream_outputs
        # under our own phase id. Surface its tier as a "do not pick again" signal —
        # P3 only fails back to P2 when topic_breadth says the prior tier was wrong.
        previous_tier = None
        if PhaseId.P2 in ctx.upstream_outputs:
            previous_tier = ctx.upstream_outputs[PhaseId.P2].get("tier")

        body_excerpt = _truncate(pack.body_markdown, BODY_EXCERPT_MAX_CHARS)
        prompt = render(
            "p2_layer/extract.md",
            source_pack=pack,
            body_excerpt=body_excerpt,
            angle=angle,
            scout_suggested_layer=scout_suggested,
            previous_tier=previous_tier,
        )

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P2_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.4,  # lower temp — this is classification, not creative
                max_tokens=600,
            )
        )

        profile = _parse_layer_profile(resp.parsed_json, resp.text)
        return profile.model_dump(mode="json")

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        profile = LayerProfile.model_validate(output)
        gates: list[QAGate] = [
            _gate_duration_in_range(profile),
            _gate_scene_count_in_range(profile),
            _gate_export_formats_non_empty(profile),
            _gate_scores_in_bounds(profile),
        ]
        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


def _parse_layer_profile(parsed_json: dict | None, raw_text: str) -> LayerProfile:
    candidate: dict | None = parsed_json
    if candidate is None:
        from llmx_advocate.core.phases.p1_5_angle import _extract_first_json_object
        candidate = _extract_first_json_object(raw_text)
    if candidate is None:
        raise _LayerExtractionError(f"LLM did not return parseable JSON. raw: {raw_text[:200]}...")

    try:
        return LayerProfile.model_validate(candidate)
    except Exception as e:
        raise _LayerExtractionError(f"LLM JSON did not match LayerProfile schema: {e}") from e


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3) :]
    return f"{head}\n\n... [truncated {len(text) - max_chars} chars] ...\n\n{tail}"


# === gates ===


def _gate_duration_in_range(profile: LayerProfile) -> QAGate:
    lo, hi = TIER_DURATION_RANGE[profile.tier]
    passed = lo <= profile.target_duration_seconds <= hi
    return QAGate(
        gate_id="P2_duration_matches_tier",
        name=f"target_duration 在 {profile.tier} 层范围内",
        passed=passed,
        rationale=(
            f"duration={profile.target_duration_seconds}s outside [{lo}, {hi}] for tier={profile.tier}"
            if not passed
            else "ok"
        ),
    )


def _gate_scene_count_in_range(profile: LayerProfile) -> QAGate:
    lo, hi = TIER_SCENE_RANGE[profile.tier]
    passed = lo <= profile.target_scene_count <= hi
    return QAGate(
        gate_id="P2_scene_count_matches_tier",
        name=f"scene 数 在 {profile.tier} 层范围内",
        passed=passed,
        rationale=(
            f"scene_count={profile.target_scene_count} outside [{lo}, {hi}] for tier={profile.tier}"
            if not passed
            else "ok"
        ),
    )


def _gate_export_formats_non_empty(profile: LayerProfile) -> QAGate:
    passed = len(profile.export_formats) >= 1
    return QAGate(
        gate_id="P2_export_formats_set",
        name="export_formats 非空",
        passed=passed,
        rationale="no export format selected" if not passed else "ok",
    )


def _gate_scores_in_bounds(profile: LayerProfile) -> QAGate:
    scores = profile.characteristic_scores.model_dump()
    bad = [k for k, v in scores.items() if not (1 <= v <= 5)]
    passed = not bad
    return QAGate(
        gate_id="P2_scores_in_1_to_5",
        name="6 维特性分都在 1-5",
        passed=passed,
        rationale=f"scores out of bounds: {bad}" if not passed else "ok",
    )
