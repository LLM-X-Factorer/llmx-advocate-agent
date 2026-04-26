from __future__ import annotations

import json
import re

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import Angle, PhaseId, QAGate, QAResult, SourcePack
from llmx_advocate.core.prompts import render
from llmx_advocate.core.qa.judges import judge_with_template

BODY_EXCERPT_MAX_CHARS = 6000

P15_SYSTEM = (
    "You are an analyst working under the chinese-content-workflow SOP. "
    "You read source material and pick the *angle* — the specific debate, contradiction, "
    "or counterintuitive claim worth a video. You return strict JSON, no commentary."
)


class _AngleExtractionError(RuntimeError):
    """Raised when the LLM response can't be parsed into an Angle."""


class P1_5Angle(Phase):
    """P1.5 — Topic Angle Discovery.

    Reads SourcePack from upstream P1, asks an LLM to pick an angle (controversy /
    counterintuitive data / underdog / contradiction / expert disagreement) and
    returns Angle.

    Two QA gates:
      - P1.5_has_community_signal (rule): pack must carry a community signal —
        either scout_analysis.controversy_signals or a "评论" / "讨论" section in body.
      - P1.5_not_product_announcement (judge): the angle must not be a plain
        product/news announcement frame.

    On retry exhaustion → fallback to P1 (the input pack itself isn't workable).
    """

    phase_id = PhaseId.P1_5
    fallback_target = PhaseId.P1

    async def run(self, ctx: TaskContext) -> dict:
        pack_dict = ctx.upstream_outputs[PhaseId.P1]
        pack = SourcePack.model_validate(pack_dict)

        body_excerpt = _truncate(pack.body_markdown, BODY_EXCERPT_MAX_CHARS)
        prompt = render("p1_5_angle/extract.md", source_pack=pack, body_excerpt=body_excerpt)

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P15_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.7,
                max_tokens=800,
            )
        )

        angle = _parse_angle(resp.parsed_json, resp.text)
        return angle.model_dump()

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        angle = Angle.model_validate(output)

        gates: list[QAGate] = [
            _gate_has_community_signal(pack),
            await _gate_not_product_announcement(angle),
        ]
        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === parsing helpers ===


def _parse_angle(parsed_json: dict | None, raw_text: str) -> Angle:
    candidate: dict | None = parsed_json
    if candidate is None:
        candidate = _extract_first_json_object(raw_text)
    if candidate is None:
        raise _AngleExtractionError(f"LLM did not return parseable JSON. raw: {raw_text[:200]}...")

    try:
        return Angle.model_validate(candidate)
    except Exception as e:
        raise _AngleExtractionError(f"LLM JSON did not match Angle schema: {e}") from e


def _extract_first_json_object(text: str) -> dict | None:
    """Salvage a JSON object from text wrapped in ```json ... ``` fences or prose."""
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3) :]
    return f"{head}\n\n... [truncated {len(text) - max_chars} chars] ...\n\n{tail}"


# === gates ===


def _gate_has_community_signal(pack: SourcePack) -> QAGate:
    has_scout = bool(pack.scout_analysis and pack.scout_analysis.controversy_signals)
    body_lower = pack.body_markdown.lower()
    has_section = any(
        marker in body_lower
        for marker in ("## 评论", "## 讨论", "## 相关讨论", "## comments", "## discussion")
    )

    passed = has_scout or has_section
    rationale = (
        "ok"
        if passed
        else "pack lacks community signal: no scout controversy_signals and no '评论/讨论' section in body"
    )
    return QAGate(
        gate_id="P1.5_has_community_signal",
        name="pack 含有社区讨论信号",
        passed=passed,
        rationale=rationale,
    )


async def _gate_not_product_announcement(angle: Angle) -> QAGate:
    judge = await judge_with_template(
        "p1_5_angle/judges.md#P1.5_not_product_announcement",
        angle=angle,
    )
    return QAGate(
        gate_id="P1.5_not_product_announcement",
        name="angle 不是产品发布通报",
        passed=judge["passed"],
        rationale=judge.get("rationale", "—"),
    )
