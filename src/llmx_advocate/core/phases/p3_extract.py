from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import (
    CoreInfo,
    DeepThinking,
    Judgment,
    LayerProfile,
    PhaseId,
    QAGate,
    QAResult,
    SourcePack,
    Tier,
)
from llmx_advocate.core.phases.p1_5_angle import _extract_first_json_object
from llmx_advocate.core.prompts import render
from llmx_advocate.core.qa.judges import judge_with_template

BODY_EXCERPT_MAX_CHARS = 6000
MIN_RICHNESS_DIMS = 3
MIN_FINDINGS = 3
MAX_FINDINGS = 5

P3_SYSTEM = (
    "You extract structured material from source content for a Bilibili "
    "video pipeline: findings, data, stories, quotes, authority anchors, "
    "pain points, and an advocate interpretation. Chinese output. Strict JSON."
)


class _ExtractionError(RuntimeError):
    pass


class P3Extract(Phase):
    """P3 — Core Information Extraction.

    QA gates:
      - P3_findings_count_in_range  (rule: 3 ≤ findings ≤ 5)
      - P3_findings_have_data       (rule: each finding has key_data or source)
      - P3_material_richness        (rule: ≥3 of 5 material dims non-empty)
      - P3_topic_breadth            (judge, skipped when tier=转化)
    """

    phase_id = PhaseId.P3
    fallback_target = None

    async def run(self, ctx: TaskContext) -> dict:
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        judgment = Judgment.model_validate(ctx.upstream_outputs[PhaseId.P2_5])
        deep = DeepThinking.model_validate(ctx.upstream_outputs[PhaseId.P2_6])

        body_excerpt = _truncate(pack.body_markdown, BODY_EXCERPT_MAX_CHARS)
        prompt = render(
            "p3_extract/extract.md",
            source_pack=pack,
            body_excerpt=body_excerpt,
            judgment=judgment,
            theme=deep.theme,
        )

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P3_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.5,
                max_tokens=1500,
            )
        )

        info = _parse_core_info(resp.parsed_json, resp.text)
        return info.model_dump()

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        info = CoreInfo.model_validate(output)
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        layer = LayerProfile.model_validate(ctx.upstream_outputs[PhaseId.P2])
        deep = DeepThinking.model_validate(ctx.upstream_outputs[PhaseId.P2_6])

        gates: list[QAGate] = [
            _gate_findings_count(info),
            _gate_findings_have_data(info),
            _gate_material_richness(info),
        ]
        # Topic breadth is meaningless for the conversion-tier (audience is intentionally narrow).
        if layer.tier != Tier.ZHUANHUA:
            gates.append(await _gate_topic_breadth(pack, layer, deep))

        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === parsing ===


def _parse_core_info(parsed_json: dict | None, raw_text: str) -> CoreInfo:
    candidate = parsed_json or _extract_first_json_object(raw_text)
    if candidate is None:
        raise _ExtractionError(f"LLM did not return parseable JSON. raw: {raw_text[:200]}...")
    try:
        return CoreInfo.model_validate(candidate)
    except Exception as e:
        raise _ExtractionError(f"LLM JSON did not match CoreInfo schema: {e}") from e


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3) :]
    return f"{head}\n\n... [truncated {len(text) - max_chars} chars] ...\n\n{tail}"


# === gates ===


def _gate_findings_count(info: CoreInfo) -> QAGate:
    n = len(info.findings)
    passed = MIN_FINDINGS <= n <= MAX_FINDINGS
    return QAGate(
        gate_id="P3_findings_count_in_range",
        name=f"findings 数量在 [{MIN_FINDINGS}, {MAX_FINDINGS}]",
        passed=passed,
        rationale="ok" if passed else f"findings count = {n}",
    )


def _gate_findings_have_data(info: CoreInfo) -> QAGate:
    """Each finding should be backed by key_data or a source citation."""
    bad = [
        i for i, f in enumerate(info.findings)
        if not (f.key_data or f.source)
    ]
    passed = not bad
    return QAGate(
        gate_id="P3_findings_have_data",
        name="每条 finding 至少有 key_data 或 source",
        passed=passed,
        rationale="ok" if passed else f"findings without data/source: indices {bad}",
        evidence={"missing_indices": bad} if bad else None,
    )


def _gate_material_richness(info: CoreInfo) -> QAGate:
    """5-dimension material check from dbs-hook (spec §5.6)."""
    has_data = bool(info.key_data_points) or any(f.key_data for f in info.findings)
    has_story = bool(info.stories)
    has_quote = bool(info.quotable_lines)
    has_authority = bool(info.authority_anchors)
    has_pain = bool(info.pain_points)

    dims = {
        "data": has_data,
        "story": has_story,
        "quote": has_quote,
        "authority": has_authority,
        "pain": has_pain,
    }
    covered = sum(1 for v in dims.values() if v)
    passed = covered >= MIN_RICHNESS_DIMS

    return QAGate(
        gate_id="P3_material_richness",
        name=f"5 维素材至少 {MIN_RICHNESS_DIMS} 维非空",
        passed=passed,
        rationale=(
            f"ok ({covered}/5)"
            if passed
            else f"only {covered}/5 dims covered: {[k for k, v in dims.items() if v]}"
        ),
        evidence={"dim_coverage": dims, "covered_count": covered},
    )


async def _gate_topic_breadth(pack: SourcePack, layer: LayerProfile, deep: DeepThinking) -> QAGate:
    j = await judge_with_template(
        "p3_extract/judges.md#P3_topic_breadth",
        source_title=pack.source.title,
        theme=deep.theme,
        tier=str(layer.tier.value),
    )
    return QAGate(
        gate_id="P3_topic_breadth",
        name="选题受众面不过窄",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )
