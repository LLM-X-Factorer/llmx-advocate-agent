from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import (
    CoreInfo,
    Judgment,
    LayerProfile,
    PhaseId,
    Publishing,
    QAGate,
    QAResult,
    VideoJSON,
)
from llmx_advocate.core.phases.p1_5_angle import _extract_first_json_object
from llmx_advocate.core.prompts import render
from llmx_advocate.core.qa.judges import judge_with_template
from llmx_advocate.core.qa.rules import char_count_chinese

TITLE_MIN_CHARS = 15
TITLE_MAX_CHARS = 38
DESCRIPTION_MIN_CHARS = 60
DESCRIPTION_MAX_CHARS = 280

# Title clickbait blacklist — these phrases scream "content farm".
TITLE_CLICKBAIT_BLACKLIST = (
    "震惊！",
    "震惊!",
    "你绝对想不到",
    "全网最",
    "建议收藏",
    "速看",
    "必看",
)

P6_SYSTEM = (
    "You write Bilibili video titles, descriptions and a pinned-comment "
    "table-of-contents from upstream phase outputs. Chinese output. Strict "
    "JSON. Title length 20-35 Chinese chars; titles must reflect the core "
    "P2.5 judgment, not just restate the topic."
)


class _PublishingExtractionError(RuntimeError):
    pass


class P6Publishing(Phase):
    """P6 — Auxiliary Output (titles / description / pinned timestamps).

    Last phase of the SOP. QA gates:
      - P6_title_count           (rule: 2-3 titles)
      - P6_title_length          (rule: each 20-35 Chinese chars)
      - P6_no_clickbait          (rule: blacklist scan)
      - P6_description_format    (rule: emoji bullets + length)
      - P6_pinned_has_timestamps (rule: at least 2 mm:ss markers)
      - P6_title_reflects_judgment (judge)
      - P6_title_matches_tier      (judge)

    On retry exhaustion → no fallback (P6 is last; failing here = task fail).
    """

    phase_id = PhaseId.P6
    fallback_target = None

    async def run(self, ctx: TaskContext) -> dict:
        judgment = Judgment.model_validate(ctx.upstream_outputs[PhaseId.P2_5])
        layer = LayerProfile.model_validate(ctx.upstream_outputs[PhaseId.P2])
        info = CoreInfo.model_validate(ctx.upstream_outputs[PhaseId.P3])
        video = VideoJSON.model_validate(ctx.upstream_outputs[PhaseId.P4])
        deep = ctx.upstream_outputs[PhaseId.P2_6]

        chapter_timestamps = _compute_chapter_timestamps(video)

        prompt = render(
            "p6_publishing/extract.md",
            theme=deep.get("theme", ""),
            judgment_full=judgment.full_sentence,
            tier=str(layer.tier.value),
            key_data_points=info.key_data_points,
            quotable_lines=info.quotable_lines,
            chapter_timestamps=chapter_timestamps,
        )

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P6_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.6,
                max_tokens=1500,
            )
        )

        publishing = _parse_publishing(resp.parsed_json, resp.text)
        return publishing.model_dump()

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        publishing = Publishing.model_validate(output)
        judgment = Judgment.model_validate(ctx.upstream_outputs[PhaseId.P2_5])
        layer = LayerProfile.model_validate(ctx.upstream_outputs[PhaseId.P2])

        gates: list[QAGate] = [
            _gate_title_count(publishing),
            _gate_title_length(publishing),
            _gate_no_clickbait(publishing),
            _gate_description_format(publishing),
            _gate_pinned_has_timestamps(publishing),
            await _gate_title_reflects_judgment(publishing, judgment),
            await _gate_title_matches_tier(publishing, layer),
        ]
        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === parsing ===


def _parse_publishing(parsed_json: dict | None, raw_text: str) -> Publishing:
    candidate = parsed_json or _extract_first_json_object(raw_text)
    if candidate is None:
        raise _PublishingExtractionError(
            f"LLM did not return parseable JSON. raw: {raw_text[:200]}..."
        )
    try:
        return Publishing.model_validate(candidate)
    except Exception as e:
        raise _PublishingExtractionError(
            f"LLM JSON did not match Publishing schema: {e}"
        ) from e


# === chapter timestamp helper ===


def _compute_chapter_timestamps(video: VideoJSON) -> list[dict]:
    """Walk the scenes, accumulate duration, emit one entry per chapter_transition.

    Returns [{title, timestamp}] where timestamp is "MM:SS".
    """
    out: list[dict] = []
    cumulative = 0
    for s in video.scenes:
        if s.get("scene_type") == "chapter_transition":
            mm = cumulative // 60
            ss = cumulative % 60
            out.append(
                {
                    "title": s.get("chapter_title") or s.get("title") or "章节",
                    "timestamp": f"{mm:02d}:{ss:02d}",
                }
            )
        cumulative += int(s.get("duration_seconds") or 0)
    return out


# === rule gates ===


def _gate_title_count(p: Publishing) -> QAGate:
    n = len(p.titles)
    passed = 2 <= n <= 3
    return QAGate(
        gate_id="P6_title_count",
        name="标题选项 2-3 个",
        passed=passed,
        rationale="ok" if passed else f"got {n} titles",
    )


def _gate_title_length(p: Publishing) -> QAGate:
    bad: list[dict] = []
    for i, t in enumerate(p.titles):
        n = char_count_chinese(t.text)
        if not (TITLE_MIN_CHARS <= n <= TITLE_MAX_CHARS):
            bad.append({"index": i, "chars": n, "text": t.text[:50]})
    passed = not bad
    return QAGate(
        gate_id="P6_title_length",
        name=f"每条标题 {TITLE_MIN_CHARS}-{TITLE_MAX_CHARS} 字",
        passed=passed,
        rationale="ok" if passed else f"{len(bad)} titles out of range",
        evidence={"bad_titles": bad} if bad else None,
    )


def _gate_no_clickbait(p: Publishing) -> QAGate:
    bad: list[dict] = []
    for i, t in enumerate(p.titles):
        for phrase in TITLE_CLICKBAIT_BLACKLIST:
            if phrase in t.text:
                bad.append({"index": i, "matched": phrase})
                break
    passed = not bad
    return QAGate(
        gate_id="P6_no_clickbait",
        name="标题不含农场标题党短语",
        passed=passed,
        rationale="ok" if passed else f"{len(bad)} titles contain clickbait",
        evidence={"hits": bad} if bad else None,
    )


def _gate_description_format(p: Publishing) -> QAGate:
    n = char_count_chinese(p.description)
    length_ok = DESCRIPTION_MIN_CHARS <= n <= DESCRIPTION_MAX_CHARS
    has_emoji_bullet = any(emoji in p.description for emoji in ("📊", "🔍", "💡", "🎯", "💬"))
    passed = length_ok and has_emoji_bullet
    return QAGate(
        gate_id="P6_description_format",
        name="简介结构（emoji 看点 + 长度）",
        passed=passed,
        rationale=(
            "ok"
            if passed
            else f"length={n} (need {DESCRIPTION_MIN_CHARS}-{DESCRIPTION_MAX_CHARS}), "
                 f"has_emoji_bullet={has_emoji_bullet}"
        ),
    )


def _gate_pinned_has_timestamps(p: Publishing) -> QAGate:
    text = p.pinned_comment or ""
    import re
    timestamps = re.findall(r"\b\d{2}:\d{2}\b", text)
    passed = len(timestamps) >= 2
    return QAGate(
        gate_id="P6_pinned_has_timestamps",
        name="置顶评论含 ≥2 个时间戳",
        passed=passed,
        rationale="ok" if passed else f"only {len(timestamps)} mm:ss markers found",
        evidence={"found": timestamps} if not passed else None,
    )


# === judge gates ===


async def _gate_title_reflects_judgment(p: Publishing, judgment: Judgment) -> QAGate:
    titles_block = "\n".join(f"- {t.text}" for t in p.titles)
    j = await judge_with_template(
        "p6_publishing/judges.md#P6_title_reflects_judgment",
        judgment_full=judgment.full_sentence,
        titles_block=titles_block,
    )
    return QAGate(
        gate_id="P6_title_reflects_judgment",
        name="标题体现核心判断",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_title_matches_tier(p: Publishing, layer: LayerProfile) -> QAGate:
    titles_block = "\n".join(f"- {t.text}" for t in p.titles)
    j = await judge_with_template(
        "p6_publishing/judges.md#P6_title_matches_tier",
        tier=str(layer.tier.value),
        titles_block=titles_block,
    )
    return QAGate(
        gate_id="P6_title_matches_tier",
        name=f"标题风格匹配 tier={layer.tier.value}",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )
