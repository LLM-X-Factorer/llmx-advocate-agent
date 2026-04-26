from __future__ import annotations

import re

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.models import (
    PhaseId,
    QAGate,
    QAResult,
    ValidationReport,
    VideoJSON,
)
from llmx_advocate.core.qa.judges import judge_with_template
from llmx_advocate.core.qa.rules import char_count_chinese, expected_duration

DURATION_HARD_CAP_S = 40.0  # spec §5.4.3 sync_5
DURATION_FORMULA_TOLERANCE_S = 3.0
SINGLE_CARD_VISUAL_TYPES = {"insight_card", "concept_card", "question_card"}

# Anti-AI smell tunables (spec §5.5)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"  # incl. ⭐ (U+2B50)
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "]"
)
PARALLEL_BOLD_BLOCK_PATTERN = re.compile(
    r"(?:^|\n)\s*\*\*[^*\n]+\*\*\s*\n.*?(?=\n\s*\*\*[^*\n]+\*\*\s*\n)",
    re.DOTALL,
)
ENUMERATION_PATTERN = re.compile(r"第[一二三四五六七八九十]")
IMPERATIVE_FILLERS = ("请你记住", "真相是", "大家一定要", "你必须知道", "注意了")
EXCEPT_SCENE_TYPES_FOR_EMOJI = {"cover", "chapter_transition", "outro"}


class P5SelfCheck(Phase):
    """P5 — JSON Self-Check.

    Pure validation: no LLM generation. Two judge calls (sync_one_focus per
    flagged scene + continuity sample + public_verifiable_language sample).

    Failure modes:
      - schema / duration / structural errors → fallback to P4 to regenerate
      - sync warnings + AI smell → also fallback (the JSON is structurally
        intact but semantically off)
    """

    phase_id = PhaseId.P5
    fallback_target = PhaseId.P4

    async def run(self, ctx: TaskContext) -> dict:
        video = VideoJSON.model_validate(ctx.upstream_outputs[PhaseId.P4])

        scenes = video.scenes
        total_duration = sum(int(s.get("duration_seconds") or 0) for s in scenes)
        tts_total = sum(char_count_chinese(s.get("tts_text") or "") for s in scenes)
        scene_type_dist: dict[str, int] = {}
        for s in scenes:
            t = s.get("scene_type", "unknown")
            scene_type_dist[t] = scene_type_dist.get(t, 0) + 1

        sync_warnings: list[str] = []
        for w in _collect_sync_rule_warnings(video):
            sync_warnings.append(w)

        report = ValidationReport(
            syntax_ok=True,
            sync_warnings=sync_warnings,
            duration_total=total_duration,
            tts_total_chars=tts_total,
            scene_type_distribution=scene_type_dist,
        )
        return report.model_dump()

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        video = VideoJSON.model_validate(ctx.upstream_outputs[PhaseId.P4])

        gates: list[QAGate] = []

        # 6 sync rules (§5.4.3)
        gates.append(_sync_2_visual_priority(video))
        gates.append(_sync_3_card_split(video))
        gates.append(_sync_5_duration_cap(video))
        gates.append(await _sync_1_one_focus(video))
        gates.append(await _sync_6_continuity(video))

        # Structural completeness (§5.4.4)
        gates.append(_gate_has_outro(video))
        gates.append(_gate_per_scene_duration_strict(video))

        # 5 anti-AI smell (§5.5)
        gates.append(_gate_no_emoji_stack(video))
        gates.append(_gate_no_parallel_bold_blocks(video))
        gates.append(_gate_no_mechanical_enumeration(video))
        gates.append(_gate_no_imperative_filler(video))
        gates.append(await _gate_public_verifiable_language(video))

        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


# === sync rule helpers ===


def _scene_visual(s: dict) -> dict | None:
    visual = s.get("visual")
    if isinstance(visual, dict):
        return visual
    return None


def _all_tts_text(video: VideoJSON) -> str:
    return "\n".join(s.get("tts_text", "") or "" for s in video.scenes)


def _collect_sync_rule_warnings(video: VideoJSON) -> list[str]:
    """Surface sync issues into ValidationReport.sync_warnings (informational)."""
    warnings = []
    for i, s in enumerate(video.scenes):
        # Duration cap is independent of visual layer.
        if (s.get("duration_seconds") or 0) > DURATION_HARD_CAP_S:
            warnings.append(
                f"scene[{i}] duration={s.get('duration_seconds')}s 超过硬上限 {DURATION_HARD_CAP_S}s"
            )

        v = _scene_visual(s)
        if v is None:
            continue
        vtype = v.get("type", "bullets")
        if vtype != "bullets" and s.get("bullets"):
            warnings.append(
                f"scene[{i}] visual.type={vtype} 但同时有 bullets 字段（不会展示）"
            )
        if vtype in SINGLE_CARD_VISUAL_TYPES and len(s.get("bullets") or []) > 1:
            warnings.append(
                f"scene[{i}] visual.type={vtype} 单卡片但有 {len(s['bullets'])} 个 bullets"
            )
    return warnings


def _sync_2_visual_priority(video: VideoJSON) -> QAGate:
    bad: list[int] = []
    for i, s in enumerate(video.scenes):
        v = _scene_visual(s)
        if v is None:
            continue
        if v.get("type", "bullets") != "bullets" and s.get("bullets"):
            bad.append(i)
    passed = not bad
    return QAGate(
        gate_id="P5_sync_visual_priority",
        name="非 bullets visual 时不应同时填 bullets 字段",
        passed=passed,
        rationale="ok" if passed else f"scenes with conflicting bullets: {bad}",
        evidence={"bad_indices": bad} if bad else None,
    )


def _sync_3_card_split(video: VideoJSON) -> QAGate:
    bad: list[int] = []
    for i, s in enumerate(video.scenes):
        v = _scene_visual(s)
        if v is None:
            continue
        if v.get("type") in SINGLE_CARD_VISUAL_TYPES and len(s.get("bullets") or []) > 1:
            bad.append(i)
    passed = not bad
    return QAGate(
        gate_id="P5_sync_card_split",
        name="单卡片 visual + 多 bullets 不允许（应拆分 scene）",
        passed=passed,
        rationale="ok" if passed else f"single-card scenes with multi bullets: {bad}",
        evidence={"bad_indices": bad} if bad else None,
    )


def _sync_5_duration_cap(video: VideoJSON) -> QAGate:
    bad = [
        i for i, s in enumerate(video.scenes)
        if (s.get("duration_seconds") or 0) > DURATION_HARD_CAP_S
    ]
    passed = not bad
    return QAGate(
        gate_id="P5_sync_duration_cap",
        name=f"无 scene duration > {DURATION_HARD_CAP_S}s（应拆分）",
        passed=passed,
        rationale="ok" if passed else f"over-long scenes: {bad}",
        evidence={"bad_indices": bad} if bad else None,
    )


async def _sync_1_one_focus(video: VideoJSON) -> QAGate:
    """Judge each non-bullets visual scene to ensure tts only covers visual content.

    To bound LLM calls, only flag scenes where visual.type is single-card AND
    tts_text contains numbered enumeration (heuristic for multi-topic talk).
    Other scenes get a free pass.
    """
    flagged: list[tuple[int, dict]] = []
    for i, s in enumerate(video.scenes):
        v = _scene_visual(s)
        if v is None:
            continue
        if v.get("type") not in SINGLE_CARD_VISUAL_TYPES:
            continue
        tts = s.get("tts_text") or ""
        if len(ENUMERATION_PATTERN.findall(tts)) >= 2:
            flagged.append((i, s))

    if not flagged:
        return QAGate(
            gate_id="P5_sync_one_focus",
            name="单卡 visual 的 tts 只讲画面内容",
            passed=True,
            rationale="no flagged scenes",
        )

    # Judge the worst offender (the first flagged one) to keep cost bounded.
    idx, s = flagged[0]
    v = s.get("visual", {}) or {}
    j = await judge_with_template(
        "p5_self_check/judges.md#P5_sync_one_focus",
        scene_type=s.get("scene_type", "?"),
        visual_type=v.get("type", "?"),
        visual_summary=str({k: v.get(k) for k in ("title", "content", "number") if v.get(k)}),
        tts_text=(s.get("tts_text") or "")[:500],
    )
    return QAGate(
        gate_id="P5_sync_one_focus",
        name="单卡 visual 的 tts 只讲画面内容",
        passed=j["passed"],
        rationale=f"scene[{idx}]: {j.get('rationale', '—')}",
        evidence={"flagged_indices": [i for i, _ in flagged]},
    )


async def _sync_6_continuity(video: VideoJSON) -> QAGate:
    """Sample 3 consecutive content/transition scenes mid-video and judge continuity."""
    candidates = [
        (i, s) for i, s in enumerate(video.scenes)
        if s.get("scene_type") in ("content", "chapter_transition", "comparison")
        and s.get("tts_text")
    ]
    if len(candidates) < 3:
        return QAGate(
            gate_id="P5_sync_continuity",
            name="跨 scene tts 连贯性",
            passed=True,
            rationale="not enough scenes to sample (skipped)",
        )

    a, b, c = candidates[len(candidates) // 2 - 1 : len(candidates) // 2 + 2]

    j = await judge_with_template(
        "p5_self_check/judges.md#P5_sync_continuity",
        idx_a=a[0], type_a=a[1].get("scene_type", "?"), tts_a=(a[1].get("tts_text") or "")[:400],
        idx_b=b[0], type_b=b[1].get("scene_type", "?"), tts_b=(b[1].get("tts_text") or "")[:400],
        idx_c=c[0], type_c=c[1].get("scene_type", "?"), tts_c=(c[1].get("tts_text") or "")[:400],
    )
    return QAGate(
        gate_id="P5_sync_continuity",
        name="跨 scene tts 连贯性（采样 3 段）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )


# === Structural ===


def _gate_has_outro(video: VideoJSON) -> QAGate:
    """Last scene must be outro and contain the channel sign-off."""
    if not video.scenes:
        return QAGate(
            gate_id="P5_structure_has_outro",
            name="末尾是 outro 含频道结尾语",
            passed=False,
            rationale="empty scenes",
        )
    last = video.scenes[-1]
    is_outro = last.get("scene_type") == "outro"
    has_signoff = "我们下期见" in (last.get("tts_text") or "")
    passed = is_outro and has_signoff
    return QAGate(
        gate_id="P5_structure_has_outro",
        name="末尾是 outro 含频道结尾语",
        passed=passed,
        rationale=(
            "ok"
            if passed
            else f"last scene_type={last.get('scene_type')}, has '我们下期见': {has_signoff}"
        ),
    )


def _gate_per_scene_duration_strict(video: VideoJSON) -> QAGate:
    """P4 already validates this; P5 re-runs as a sanity check (no surprises in store)."""
    bad: list[dict] = []
    for i, s in enumerate(video.scenes):
        tts = s.get("tts_text") or ""
        if not tts:
            continue
        expected = expected_duration(tts)
        actual = s.get("duration_seconds") or 0
        if abs(actual - expected) > DURATION_FORMULA_TOLERANCE_S:
            bad.append({"index": i, "expected": round(expected, 1), "actual": actual})
    passed = not bad
    return QAGate(
        gate_id="P5_per_scene_duration_strict",
        name=f"每 scene duration 仍符合公式 (±{DURATION_FORMULA_TOLERANCE_S}s)",
        passed=passed,
        rationale="ok" if passed else f"{len(bad)} scenes off-formula",
        evidence={"off_scenes": bad[:5]} if bad else None,
    )


# === Anti-AI smell (§5.5) ===


def _gate_no_emoji_stack(video: VideoJSON) -> QAGate:
    bad: list[int] = []
    for i, s in enumerate(video.scenes):
        if s.get("scene_type") in EXCEPT_SCENE_TYPES_FOR_EMOJI:
            continue
        tts = s.get("tts_text") or ""
        if len(EMOJI_PATTERN.findall(tts)) >= 2:
            bad.append(i)
    passed = not bad
    return QAGate(
        gate_id="P5_no_emoji_stack",
        name="单 scene tts 内 emoji 数量 ≤ 1（封面 / 章节页 / outro 例外）",
        passed=passed,
        rationale="ok" if passed else f"emoji-heavy scenes: {bad}",
    )


def _gate_no_parallel_bold_blocks(video: VideoJSON) -> QAGate:
    full_text = _all_tts_text(video)
    matches = PARALLEL_BOLD_BLOCK_PATTERN.findall(full_text)
    passed = len(matches) < 3
    return QAGate(
        gate_id="P5_no_parallel_bold_blocks",
        name="不允许 ≥3 段连续的加粗标题列表块",
        passed=passed,
        rationale="ok" if passed else f"{len(matches)} parallel bold blocks detected",
    )


def _gate_no_mechanical_enumeration(video: VideoJSON) -> QAGate:
    """'第一/第二/第三' 句式整片出现 ≤ 2 组（spec §5.5)."""
    full_text = _all_tts_text(video)
    matches = ENUMERATION_PATTERN.findall(full_text)
    # Each "group" is 3 consecutive enumeration markers ≈ 第一+第二+第三. Count groups by /3.
    groups = len(matches) // 3
    passed = groups <= 2
    return QAGate(
        gate_id="P5_no_mechanical_enumeration",
        name='机械"第一/第二/第三" 整片 ≤ 2 组',
        passed=passed,
        rationale="ok" if passed else f"{groups} enumeration groups (>2)",
        evidence={"enum_groups": groups, "raw_count": len(matches)},
    )


def _gate_no_imperative_filler(video: VideoJSON) -> QAGate:
    full_text = _all_tts_text(video)
    hits: list[str] = [p for p in IMPERATIVE_FILLERS if p in full_text]
    passed = not hits
    return QAGate(
        gate_id="P5_no_imperative_filler",
        name="不允许 AI 祈使句习惯（'请你记住' / '真相是' 等）",
        passed=passed,
        rationale="ok" if passed else f"matched: {hits}",
        evidence={"matched": hits} if hits else None,
    )


async def _gate_public_verifiable_language(video: VideoJSON) -> QAGate:
    sample = _all_tts_text(video)[:2000]
    j = await judge_with_template(
        "p5_self_check/judges.md#P5_public_verifiable_language",
        tts_sample=sample,
    )
    return QAGate(
        gate_id="P5_public_verifiable_language",
        name="语言公共可验证（无私语、抽象有兑现）",
        passed=j["passed"],
        rationale=j.get("rationale", "—"),
    )
