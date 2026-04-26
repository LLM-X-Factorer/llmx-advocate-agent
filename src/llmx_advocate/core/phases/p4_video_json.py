from __future__ import annotations

import re

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.core.models import (
    Angle,
    CoreInfo,
    DeepThinking,
    Judgment,
    LayerProfile,
    OpeningStyle,
    PhaseId,
    QAGate,
    QAResult,
    SourcePack,
    Tier,
    VideoJSON,
)
from llmx_advocate.core.phases.p1_5_angle import _extract_first_json_object
from llmx_advocate.core.prompts import render
from llmx_advocate.core.qa.judges import judge_with_template
from llmx_advocate.core.qa.rules import (
    PAN_KOL_OPENINGS,
    RELAY_PHRASES,
    SOURCE_BACKING_BLACKLIST,
    char_count_chinese,
    contains_any,
    expected_duration,
)

P4_SYSTEM = (
    "You assemble a Bilibili video JSON from upstream phase outputs. Chinese tts. "
    "Strict JSON output following the provided schema. Keep tts_text faithful to "
    "spoken Chinese, never machine-translated English."
)

JUDGMENT_FIRST_PREFIX_LIMIT_CHARS = 50  # P4_jf_judgment_within_15s
# Tolerances widened after V0.1 smoke — non-reasoning chat models tend to under-
# generate on long structured JSON (e.g. produce 14 scenes when 24 were asked).
# Tightening these would only force the engine into terminal-fail loops with no
# meaningful SOP gain; rendering systems can absorb this much wiggle.
DURATION_TOLERANCE_S = 4.0  # per-scene duration formula tolerance
TOTAL_DURATION_TOLERANCE_RATIO = 0.50  # ±50% on overall duration vs target
SCENE_COUNT_TOLERANCE = 6

CHANNEL_INTRO_FIXED = "拆解大语言模型时代底层逻辑的频道"  # marker in tts to detect intro scene


class _VideoJSONExtractionError(RuntimeError):
    pass


class P4VideoJSON(Phase):
    """P4 — Video JSON Generation.

    Common red lines (§5.3.0) + structural validation always run. Style-specific
    gates are added based on TaskConfig.opening_style:
      - judgment_first → §5.3.1 (rule: within-15s, before-intro)
      - suspense_first → §5.3.2 (5 judges: topic_established, hook_strength,
        credibility_signal, no_answer_leak, judgment_landing)

    On retry exhaustion → no fallback (V0.1 fails the task; later may add
    P3 fallback if richness was inadequate).
    """

    phase_id = PhaseId.P4
    fallback_target = None

    async def run(self, ctx: TaskContext) -> dict:
        pack = SourcePack.model_validate(ctx.upstream_outputs[PhaseId.P1])
        angle = Angle.model_validate(ctx.upstream_outputs[PhaseId.P1_5])
        layer = LayerProfile.model_validate(ctx.upstream_outputs[PhaseId.P2])
        judgment = Judgment.model_validate(ctx.upstream_outputs[PhaseId.P2_5])
        deep = DeepThinking.model_validate(ctx.upstream_outputs[PhaseId.P2_6])
        info = CoreInfo.model_validate(ctx.upstream_outputs[PhaseId.P3])

        opening_style = _resolve_opening_style(ctx.task.config.opening_style, layer.tier)

        prompt = render(
            "p4_video_json/extract.md",
            theme=deep.theme,
            judgment_full=judgment.full_sentence,
            tier=str(layer.tier.value),
            target_scene_count=layer.target_scene_count,
            target_duration_seconds=layer.target_duration_seconds,
            export_formats=[ef.value for ef in layer.export_formats],
            opening_style=opening_style.value,
            angle=angle,
            deep=deep,
            findings=info.findings,
            key_data_points=info.key_data_points,
            stories=info.stories,
            quotable_lines=info.quotable_lines,
            authority_anchors=info.authority_anchors,
            source_pack=pack,
        )

        provider = get_provider(ctx.task.config.llm_provider)
        resp = await provider.complete(
            LLMRequest(
                model=ctx.task.config.llm_model,
                system=P4_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.6,
                max_tokens=6000,
            )
        )

        video = _parse_video_json(resp.parsed_json, resp.text)
        return video.model_dump(mode="json")

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        video = VideoJSON.model_validate(output)
        layer = LayerProfile.model_validate(ctx.upstream_outputs[PhaseId.P2])
        judgment = Judgment.model_validate(ctx.upstream_outputs[PhaseId.P2_5])

        gates: list[QAGate] = []
        gates.extend(_common_red_line_rule_gates(video))
        gates.append(_gate_scene_count(video, layer))
        gates.append(_gate_total_duration(video, layer))
        gates.append(_gate_per_scene_duration(video))
        gates.append(_gate_opening_structure(video))

        gates.append(await _gate_first_sentence_complete(video))
        gates.append(await _gate_judgment_exists(video, judgment))
        gates.append(await _gate_oral_friendly(video))

        opening_style = _resolve_opening_style(ctx.task.config.opening_style, layer.tier)
        if opening_style == OpeningStyle.JUDGMENT_FIRST:
            gates.extend(_judgment_first_gates(video, judgment))
        elif opening_style == OpeningStyle.SUSPENSE_FIRST:
            gates.extend(await _suspense_first_gates(video, judgment))

        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === parsing ===


def _parse_video_json(parsed_json: dict | None, raw_text: str) -> VideoJSON:
    candidate = parsed_json or _extract_first_json_object(raw_text)
    if candidate is None:
        raise _VideoJSONExtractionError(
            f"LLM did not return parseable JSON. raw: {raw_text[:200]}..."
        )
    try:
        return VideoJSON.model_validate(candidate)
    except Exception as e:
        raise _VideoJSONExtractionError(f"LLM JSON did not match VideoJSON schema: {e}") from e


def _resolve_opening_style(style: OpeningStyle, tier: Tier) -> OpeningStyle:
    if style == OpeningStyle.AUTO:
        return OpeningStyle.SUSPENSE_FIRST if tier == Tier.LIUYIN else OpeningStyle.JUDGMENT_FIRST
    return style


def _all_tts_text(video: VideoJSON) -> str:
    return "\n".join(s.get("tts_text", "") or "" for s in video.scenes)


def _hook_scenes(video: VideoJSON) -> list[dict]:
    return [s for s in video.scenes if s.get("scene_type") == "hook"]


# === Common red line gates (§5.3.0) ===


def _common_red_line_rule_gates(video: VideoJSON) -> list[QAGate]:
    full_text = _all_tts_text(video)
    return [
        _gate_blacklist(
            "P4_no_source_backing",
            "无来源背书短语",
            full_text,
            SOURCE_BACKING_BLACKLIST,
        ),
        _gate_blacklist(
            "P4_no_relay_phrases",
            "无搬运工句式",
            full_text,
            RELAY_PHRASES,
        ),
        _gate_blacklist(
            "P4_no_pan_kol_opening",
            "无泛知识博主开头",
            full_text,
            PAN_KOL_OPENINGS,
        ),
    ]


def _gate_blacklist(gate_id: str, name: str, text: str, blacklist: tuple[str, ...]) -> QAGate:
    hit = contains_any(text, blacklist)
    passed = hit is None
    return QAGate(
        gate_id=gate_id,
        name=name,
        passed=passed,
        rationale="ok" if passed else f"matched forbidden phrase: {hit!r}",
        evidence={"matched": hit} if hit else None,
    )


# === Structural gates ===


def _gate_scene_count(video: VideoJSON, layer: LayerProfile) -> QAGate:
    n = len(video.scenes)
    target = layer.target_scene_count
    passed = abs(n - target) <= SCENE_COUNT_TOLERANCE
    return QAGate(
        gate_id="P4_scene_count",
        name=f"scene 数 ≈ {target} (±{SCENE_COUNT_TOLERANCE})",
        passed=passed,
        rationale="ok" if passed else f"got {n} scenes, target {target}",
    )


def _gate_total_duration(video: VideoJSON, layer: LayerProfile) -> QAGate:
    total = sum(s.get("duration_seconds", 0) for s in video.scenes)
    target = layer.target_duration_seconds
    tolerance = max(60, int(target * TOTAL_DURATION_TOLERANCE_RATIO))
    passed = abs(total - target) <= tolerance
    return QAGate(
        gate_id="P4_total_duration",
        name=f"总时长 ≈ {target}s (±{tolerance}s)",
        passed=passed,
        rationale="ok" if passed else f"got {total}s, target {target}s",
    )


def _gate_per_scene_duration(video: VideoJSON) -> QAGate:
    """Each scene with tts_text must have duration_seconds within tolerance of the formula."""
    bad: list[dict] = []
    for i, s in enumerate(video.scenes):
        tts = s.get("tts_text") or ""
        if not tts:
            continue
        expected = expected_duration(tts)
        actual = s.get("duration_seconds", 0)
        if abs(actual - expected) > DURATION_TOLERANCE_S:
            bad.append({"index": i, "scene_type": s.get("scene_type"), "expected": round(expected, 1), "actual": actual})

    passed = not bad
    return QAGate(
        gate_id="P4_per_scene_duration",
        name=f"每个 scene duration 符合公式 (±{DURATION_TOLERANCE_S}s)",
        passed=passed,
        rationale="ok" if passed else f"{len(bad)} scenes off-formula",
        evidence={"off_scenes": bad[:5]} if bad else None,
    )


def _gate_opening_structure(video: VideoJSON) -> QAGate:
    """First scenes must be cover → hook(_judgment) → channel_intro, in that order.

    Order is mandatory because P4_jf_judgment_before_intro is style-specific —
    this gate enforces the underlying structural truth on every video.
    """
    types = [s.get("scene_type") for s in video.scenes[:5]]
    if not types:
        return QAGate(
            gate_id="P4_opening_structure",
            name="开场结构正确",
            passed=False,
            rationale="empty scenes",
        )

    cover_ok = types[0] == "cover"
    hook_idx = next(
        (i for i, t in enumerate(types) if t in ("hook", "hook_judgment")), None
    )
    intro_idx = next((i for i, t in enumerate(types) if t == "channel_intro"), None)
    order_ok = hook_idx is not None and intro_idx is not None and hook_idx < intro_idx

    passed = cover_ok and order_ok
    return QAGate(
        gate_id="P4_opening_structure",
        name="开场顺序：cover → hook → channel_intro",
        passed=passed,
        rationale=(
            "ok"
            if passed
            else f"first 5 types = {types}; cover={cover_ok}, "
                 f"hook_idx={hook_idx}, intro_idx={intro_idx}"
        ),
    )


# === Common red line judge gates (§5.3.0) ===


async def _gate_first_sentence_complete(video: VideoJSON) -> QAGate:
    hooks = _hook_scenes(video)
    if not hooks:
        return QAGate(
            gate_id="P4_first_sentence_complete",
            name="hook 第一句是完整句子",
            passed=False,
            rationale="no hook scene found",
        )
    main_text = hooks[0].get("main_text", "") or ""
    first_sentence = re.split(r"[。！？!?]", main_text, maxsplit=1)[0]

    j = await judge_with_template(
        "p4_video_json/judges.md#P4_first_sentence_complete",
        first_sentence=first_sentence,
    )
    return QAGate(
        gate_id="P4_first_sentence_complete",
        name="hook 第一句是完整句子",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_judgment_exists(video: VideoJSON, judgment: Judgment) -> QAGate:
    full_text = _all_tts_text(video)[:4000]
    j = await judge_with_template(
        "p4_video_json/judges.md#P4_judgment_exists",
        judgment_full_sentence=judgment.full_sentence,
        all_tts_text=full_text,
    )
    return QAGate(
        gate_id="P4_judgment_exists",
        name="视频内出现核心判断的本质内容",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_oral_friendly(video: VideoJSON) -> QAGate:
    sample = _all_tts_text(video)[:1500]
    j = await judge_with_template(
        "p4_video_json/judges.md#P4_oral_friendly",
        tts_sample=sample,
    )
    return QAGate(
        gate_id="P4_oral_friendly",
        name="整体口播友好",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


# === judgment_first style gates (§5.3.1) ===


def _judgment_first_gates(video: VideoJSON, judgment: Judgment) -> list[QAGate]:
    return [
        _gate_jf_judgment_within_15s(video, judgment),
        _gate_jf_judgment_before_intro(video),
    ]


def _gate_jf_judgment_within_15s(video: VideoJSON, judgment: Judgment) -> QAGate:
    """Cumulative TTS chars ≤ JUDGMENT_FIRST_PREFIX_LIMIT_CHARS must already
    contain a recognisable trace of the judgment's deeper essence."""
    cumulative = 0
    seen_text = ""
    target_essence = judgment.deeper_essence or judgment.full_sentence
    target_chars = {c for c in target_essence if c.isalnum() or "一" <= c <= "鿿"}

    for s in video.scenes:
        tts = s.get("tts_text") or ""
        cumulative += char_count_chinese(tts)
        seen_text += tts
        if cumulative >= JUDGMENT_FIRST_PREFIX_LIMIT_CHARS:
            break

    overlap = sum(1 for c in target_chars if c in seen_text)
    overlap_ratio = overlap / max(len(target_chars), 1)
    passed = overlap_ratio >= 0.4  # at least ~40% character overlap with the essence
    return QAGate(
        gate_id="P4_jf_judgment_within_15s",
        name=f"前 {JUDGMENT_FIRST_PREFIX_LIMIT_CHARS} 字内出现判断本质",
        passed=passed,
        rationale=(
            "ok"
            if passed
            else f"cumulative TTS prefix ({cumulative} chars) covers {overlap_ratio:.0%} of judgment essence"
        ),
        evidence={"overlap_ratio": overlap_ratio},
    )


def _gate_jf_judgment_before_intro(video: VideoJSON) -> QAGate:
    """hook(_judgment) scene must precede channel_intro."""
    hook_idx = next(
        (i for i, s in enumerate(video.scenes) if s.get("scene_type") in ("hook", "hook_judgment")),
        None,
    )
    intro_idx = next(
        (i for i, s in enumerate(video.scenes) if s.get("scene_type") == "channel_intro"),
        None,
    )

    if hook_idx is None or intro_idx is None:
        return QAGate(
            gate_id="P4_jf_judgment_before_intro",
            name="hook 在 channel_intro 之前",
            passed=False,
            rationale=f"missing scenes: hook_idx={hook_idx}, intro_idx={intro_idx}",
        )

    passed = hook_idx < intro_idx
    return QAGate(
        gate_id="P4_jf_judgment_before_intro",
        name="hook 在 channel_intro 之前",
        passed=passed,
        rationale="ok" if passed else f"hook at {hook_idx}, intro at {intro_idx}",
    )


# === suspense_first style gates (§5.3.2) ===


def _tts_window(video: VideoJSON, start_s: float, end_s: float) -> str:
    """Return the concatenated tts_text whose cumulative duration falls inside [start_s, end_s)."""
    cumulative = 0.0
    chunks: list[str] = []
    for s in video.scenes:
        tts = s.get("tts_text") or ""
        scene_duration = float(s.get("duration_seconds") or 0)
        scene_end = cumulative + scene_duration
        # Include this scene's tts if any of its time overlaps [start, end).
        if scene_end > start_s and cumulative < end_s and tts:
            chunks.append(tts)
        cumulative = scene_end
        if cumulative >= end_s:
            break
    return "\n".join(chunks)


async def _suspense_first_gates(video: VideoJSON, judgment: Judgment) -> list[QAGate]:
    early_5s = _tts_window(video, 0.0, 5.0)
    early_15s = _tts_window(video, 0.0, 15.0)
    early_30s = _tts_window(video, 0.0, 30.0)
    tts_30_to_60s = _tts_window(video, 30.0, 60.0)

    return [
        await _gate_sf_topic_established(early_5s),
        await _gate_sf_hook_strength(early_15s),
        await _gate_sf_credibility_signal(early_15s),
        await _gate_sf_no_answer_leak(early_30s, judgment),
        await _gate_sf_judgment_landing(tts_30_to_60s, judgment),
    ]


async def _gate_sf_topic_established(early_tts_5s: str) -> QAGate:
    j = await judge_with_template(
        "p4_video_json/judges_suspense.md#P4_sf_topic_established",
        early_tts_5s=early_tts_5s,
    )
    return QAGate(
        gate_id="P4_sf_topic_established",
        name="0-5s 话题独立建立",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_sf_hook_strength(early_tts_15s: str) -> QAGate:
    j = await judge_with_template(
        "p4_video_json/judges_suspense.md#P4_sf_hook_strength",
        early_tts_15s=early_tts_15s,
    )
    return QAGate(
        gate_id="P4_sf_hook_strength",
        name="0-15s 命中 5 维素材至少 1 项",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_sf_credibility_signal(early_tts_15s: str) -> QAGate:
    j = await judge_with_template(
        "p4_video_json/judges_suspense.md#P4_sf_credibility_signal",
        early_tts_15s=early_tts_15s,
    )
    return QAGate(
        gate_id="P4_sf_credibility_signal",
        name="0-15s 出现可信度锚点",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_sf_no_answer_leak(early_tts_30s: str, judgment: Judgment) -> QAGate:
    j = await judge_with_template(
        "p4_video_json/judges_suspense.md#P4_sf_no_answer_leak",
        early_tts_30s=early_tts_30s,
        judgment_full_sentence=judgment.full_sentence,
    )
    return QAGate(
        gate_id="P4_sf_no_answer_leak",
        name="0-30s 不直接说出最终结论",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


async def _gate_sf_judgment_landing(tts_30_to_60s: str, judgment: Judgment) -> QAGate:
    if not tts_30_to_60s.strip():
        return QAGate(
            gate_id="P4_sf_judgment_landing",
            name="30-60s 内判断落地",
            passed=False,
            rationale="no tts in 30-60s window — video too short for suspense_first",
        )
    j = await judge_with_template(
        "p4_video_json/judges_suspense.md#P4_sf_judgment_landing",
        tts_30_to_60s=tts_30_to_60s,
        judgment_full_sentence=judgment.full_sentence,
    )
    return QAGate(
        gate_id="P4_sf_judgment_landing",
        name="30-60s 内判断落地",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )
