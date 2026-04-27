from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import (
    Angle,
    Judgment,
    LayerProfile,
    PhaseId,
    QAGate,
    QAResult,
    SourcePack,
)
from llmx_advocate.core.phases.p1_5_angle import _extract_first_json_object
from llmx_advocate.core.prompts import render
from llmx_advocate.core.qa.judges import judge_with_template
from llmx_advocate.core.qa.rules import (
    RELAY_PHRASES,
    SOURCE_BACKING_BLACKLIST,
    char_count_chinese,
    contains_any,
    count_cjk,
)

BODY_EXCERPT_MAX_CHARS = 5000
BREVITY_MAX_CHARS = 60

P2_5_SYSTEM = (
    "You are an analyst extracting the *core judgment* from source material. "
    "The judgment must be your own structural insight (not a paraphrase), "
    "able to stand on its own without the source, fit in 18 spoken seconds, "
    "and not rely on source-backing phrases. Return strict JSON, no commentary."
)


class _JudgmentExtractionError(RuntimeError):
    pass


class P2_5Judgment(Phase):
    """P2.5 — Core Judgment Extraction (the SOP's red-line phase).

    Forced 4-gate QA (spec §5.1):
      P2.5_uniqueness          (judge)
      P2.5_independent_value   (judge)
      P2.5_brevity             (rule, ≤ 50 chars ≈ 15 spoken seconds)
      P2.5_anti_relay          (rule + judge)

    Optional 5th gate enabled via TaskConfig.enable_cognition_gap_check:
      P2.5_cognition_gap       (judge)

    judgment_seed handling: scout's seed (if any) is treated as a *starting
    point*, never a finished verdict. The model can keep it (overrode_seed=False)
    or override (overrode_seed=True + override_reason). Either way the 4 gates
    run on the final full_sentence — the seed gets no immunity.

    On retry exhaustion (5 by default) → fallback to P1.5 (try a different angle).
    """

    phase_id = PhaseId.P2_5
    fallback_target = PhaseId.P1_5

    async def run(self, ctx: TaskContext) -> dict:
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        angle = Angle.model_validate(ctx.upstream_outputs[PhaseId.P1_5])
        layer_profile = LayerProfile.model_validate(ctx.upstream_outputs[PhaseId.P2])

        body_excerpt = _truncate(pack.body_markdown, BODY_EXCERPT_MAX_CHARS)
        prompt = render(
            "p2_5_judgment/extract.md",
            source_pack=pack,
            body_excerpt=body_excerpt,
            angle=angle,
            layer_profile=layer_profile,
        )

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P2_5_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.7,
                max_tokens=600,
            )
        )

        judgment = _parse_judgment(resp.parsed_json, resp.text, pack)
        return judgment.model_dump()

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        judgment = Judgment.model_validate(output)
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])

        gates: list[QAGate] = [
            _gate_brevity(judgment),
            _gate_anti_relay_rule(judgment),
            await _gate_uniqueness(judgment, pack),
            await _gate_independent_value(judgment),
            await _gate_anti_relay_judge(judgment),
        ]

        if ctx.task.config.enable_cognition_gap_check:
            gates.append(await _gate_cognition_gap(judgment, pack))

        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === parsing ===


def _parse_judgment(parsed_json: dict | None, raw_text: str, pack: SourcePack) -> Judgment:
    candidate = parsed_json or _extract_first_json_object(raw_text)
    if candidate is None:
        raise _JudgmentExtractionError(f"LLM did not return parseable JSON. raw: {raw_text[:200]}...")

    # If the model didn't echo the seed, fill it from the source pack.
    seed = pack.scout_analysis.judgment_seed if pack.scout_analysis else None
    candidate.setdefault("seed_judgment", seed)
    candidate.setdefault("overrode_seed", False)
    candidate.setdefault("override_reason", None)

    try:
        return Judgment.model_validate(candidate)
    except Exception as e:
        raise _JudgmentExtractionError(f"LLM JSON did not match Judgment schema: {e}") from e


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3) :]
    return f"{head}\n\n... [truncated {len(text) - max_chars} chars] ...\n\n{tail}"


# === gates ===


def _gate_brevity(judgment: Judgment) -> QAGate:
    n = count_cjk(judgment.full_sentence)
    passed = n <= BREVITY_MAX_CHARS
    return QAGate(
        gate_id="P2.5_brevity",
        name=f"判断 ≤ {BREVITY_MAX_CHARS} 汉字（≈18 秒口播）",
        passed=passed,
        rationale=f"full_sentence is {n} CJK chars" if not passed else "ok",
        evidence={"cjk_char_count": n, "limit": BREVITY_MAX_CHARS} if not passed else None,
    )


def _gate_anti_relay_rule(judgment: Judgment) -> QAGate:
    text = judgment.full_sentence
    hit_source = contains_any(text, SOURCE_BACKING_BLACKLIST)
    hit_relay = contains_any(text, RELAY_PHRASES)
    bad = hit_source or hit_relay
    passed = bad is None
    return QAGate(
        gate_id="P2.5_anti_relay_rule",
        name="判断不含来源背书 / 搬运工短语",
        passed=passed,
        rationale=f"contains forbidden phrase: {bad!r}" if not passed else "ok",
        evidence={"matched": bad} if not passed else None,
    )


async def _gate_uniqueness(judgment: Judgment, pack: SourcePack) -> QAGate:
    raw_summary = _truncate(pack.body_markdown, 2000)
    j = await judge_with_template(
        "p2_5_judgment/judges.md#P2.5_uniqueness",
        judgment=judgment,
        raw_material_summary=raw_summary,
    )
    return QAGate(
        gate_id="P2.5_uniqueness",
        name="独特性（不是原文复述）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_independent_value(judgment: Judgment) -> QAGate:
    j = await judge_with_template(
        "p2_5_judgment/judges.md#P2.5_independent_value",
        judgment=judgment,
    )
    return QAGate(
        gate_id="P2.5_independent_value",
        name="独立价值（不看原文也成立）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_anti_relay_judge(judgment: Judgment) -> QAGate:
    j = await judge_with_template(
        "p2_5_judgment/judges.md#P2.5_anti_relay",
        judgment=judgment,
    )
    return QAGate(
        gate_id="P2.5_anti_relay_judge",
        name="反搬运（不依赖来源背书）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_cognition_gap(judgment: Judgment, pack: SourcePack) -> QAGate:
    j = await judge_with_template(
        "p2_5_judgment/judges.md#P2.5_cognition_gap",
        topic=pack.source.title,
        judgment=judgment,
        peer_takes="（V0.1 未集成同行解读检索，本次仅基于判断本身评估深度）",
    )
    return QAGate(
        gate_id="P2.5_cognition_gap",
        name="认知落差（同行解读 vs 你的判断）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )
