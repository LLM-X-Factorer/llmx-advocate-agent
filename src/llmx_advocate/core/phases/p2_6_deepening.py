from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import (
    DeepThinking,
    Judgment,
    PhaseId,
    QAGate,
    QAResult,
    SourcePack,
)
from llmx_advocate.core.phases.p1_5_angle import _extract_first_json_object
from llmx_advocate.core.prompts import render
from llmx_advocate.core.qa.judges import judge_with_template
from llmx_advocate.core.qa.rules import char_count_chinese

BODY_EXCERPT_MAX_CHARS = 4500
THEME_MAX_CHARS = 50

P2_6_SYSTEM = (
    "You are an analyst running a three-layer deepening pass on a one-sentence "
    "judgment: ask why, ask what-it-means, then either keep or refine the theme. "
    "All output fields must be Chinese. Return strict JSON, no commentary."
)


class _DeepeningExtractionError(RuntimeError):
    pass


class P2_6Deepening(Phase):
    """P2.6 — Cognitive Deepening (information → thinking → insight).

    Verifies and possibly refines the P2.5 judgment via three rounds:
    WHY (round 1), WHAT IT MEANS (round 2), validation (round 3).

    Outputs a `theme` that downstream phases (P3+) consume as the unifying claim.

    QA — 4 Depth Tests (spec §5.2):
      P2.6_beyond_surface  (rule + judge)
      P2.6_makes_rethink   (judge)
      P2.6_transferable    (judge)
      P2.6_hook_independent (judge)

    On retry exhaustion → fallback to P2.5 (the seed judgment was too shallow).
    """

    phase_id = PhaseId.P2_6
    fallback_target = PhaseId.P2_5

    async def run(self, ctx: TaskContext) -> dict:
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        judgment = Judgment.model_validate(ctx.upstream_outputs[PhaseId.P2_5])

        body_excerpt = _truncate(pack.body_markdown, BODY_EXCERPT_MAX_CHARS)
        prompt = render(
            "p2_6_deepening/extract.md",
            source_pack=pack,
            body_excerpt=body_excerpt,
            judgment=judgment,
        )

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P2_6_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.6,
                max_tokens=900,
            )
        )

        deep = _parse_deep_thinking(resp.parsed_json, resp.text)
        return deep.model_dump()

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        deep = DeepThinking.model_validate(output)
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])

        gates: list[QAGate] = [
            _gate_theme_brevity(deep),
            _gate_beyond_surface_rule(deep),
            await _gate_beyond_surface_judge(deep),
            await _gate_makes_rethink(deep),
            await _gate_transferable(deep),
            await _gate_hook_independent(deep, pack),
        ]
        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === parsing ===


def _parse_deep_thinking(parsed_json: dict | None, raw_text: str) -> DeepThinking:
    candidate = parsed_json or _extract_first_json_object(raw_text)
    if candidate is None:
        raise _DeepeningExtractionError(
            f"LLM did not return parseable JSON. raw: {raw_text[:200]}..."
        )
    try:
        return DeepThinking.model_validate(candidate)
    except Exception as e:
        raise _DeepeningExtractionError(f"LLM JSON did not match DeepThinking schema: {e}") from e


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3) :]
    return f"{head}\n\n... [truncated {len(text) - max_chars} chars] ...\n\n{tail}"


# === gates ===

# Adjective-style red flags for P2.6_beyond_surface_rule.
SURFACE_ADJECTIVES = (
    "很厉害",
    "很重要",
    "很强大",
    "很有意思",
    "很好",
    "很棒",
    "有问题",
    "改变世界",
    "颠覆一切",
    "是未来",
)


def _gate_theme_brevity(deep: DeepThinking) -> QAGate:
    n = char_count_chinese(deep.theme)
    passed = n <= THEME_MAX_CHARS and n > 0
    return QAGate(
        gate_id="P2.6_theme_brevity",
        name=f"theme ≤ {THEME_MAX_CHARS} 汉字",
        passed=passed,
        rationale="ok" if passed else f"theme is {n} chars",
    )


def _gate_beyond_surface_rule(deep: DeepThinking) -> QAGate:
    theme = deep.theme
    matched = next((adj for adj in SURFACE_ADJECTIVES if adj in theme), None)
    passed = matched is None
    return QAGate(
        gate_id="P2.6_beyond_surface_rule",
        name="theme 不含形容词式判断（黑名单）",
        passed=passed,
        rationale="ok" if passed else f"theme contains surface-adjective phrase: {matched!r}",
        evidence={"matched": matched} if matched else None,
    )


async def _gate_beyond_surface_judge(deep: DeepThinking) -> QAGate:
    j = await judge_with_template(
        "p2_6_deepening/judges.md#P2.6_beyond_surface",
        theme=deep.theme,
    )
    return QAGate(
        gate_id="P2.6_beyond_surface_judge",
        name="theme 超越表面（结构性洞察而非形容词）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_makes_rethink(deep: DeepThinking) -> QAGate:
    j = await judge_with_template(
        "p2_6_deepening/judges.md#P2.6_makes_rethink",
        theme=deep.theme,
    )
    return QAGate(
        gate_id="P2.6_makes_rethink",
        name="theme 能让读者重新思考默认假设",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_transferable(deep: DeepThinking) -> QAGate:
    j = await judge_with_template(
        "p2_6_deepening/judges.md#P2.6_transferable",
        theme=deep.theme,
    )
    return QAGate(
        gate_id="P2.6_transferable",
        name="theme 可迁移到至少 2 个其他场景",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_hook_independent(deep: DeepThinking, pack: SourcePack) -> QAGate:
    j = await judge_with_template(
        "p2_6_deepening/judges.md#P2.6_hook_independent",
        theme=deep.theme,
        source_title=pack.source.title,
    )
    return QAGate(
        gate_id="P2.6_hook_independent",
        name="去掉热点钩子后 theme 仍成立",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )
