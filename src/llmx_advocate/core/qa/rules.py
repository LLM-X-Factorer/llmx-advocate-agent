"""Rule-based gates — pure-Python checks, no LLM.

V0.1 stub: each rule has a signature ready to be wired into core.qa.registry.
The actual phase implementations will register them via core.qa.gates.registry.register(...).
"""

from __future__ import annotations

import re

# Blacklists derived from spec §5.3.0 / §5.5.
SOURCE_BACKING_BLACKLIST = (
    "今天聊一个",
    "刚上HN热榜",
    "刚上Hacker News",
    "最近XX很火",
    "最近很火",
    "HN 热榜",
    "hacker news 热榜",
)

RELAY_PHRASES = (
    "今天聊一个",
    "今天给大家介绍",
    "我来给大家解读",
    "今天带大家看看",
    "带大家了解一下",
)

PAN_KOL_OPENINGS = (
    "Hey 各位",
    "各位B站朋友",
    "各位粉丝大家好",
    "Hey各位",
)

IMPERATIVE_FILLERS = (
    "请你记住",
    "真相是",
    "大家一定要",
    "你必须知道",
)

NUMBERING_PATTERN = re.compile(r"第[一二三四五六七八九十]|[1-9][.、]")


def contains_any(text: str, needles: tuple[str, ...]) -> str | None:
    """Return the first matching needle, or None."""
    lowered = text.lower()
    for n in needles:
        if n.lower() in lowered:
            return n
    return None


def char_count_chinese(text: str) -> int:
    """Count length suitable for TTS estimation (treat each non-whitespace char as 1)."""
    return sum(1 for c in text if not c.isspace())


def estimated_seconds(text: str) -> float:
    """3.2 chars/sec per VIDEO_JSON_REFERENCE.md."""
    return char_count_chinese(text) / 3.2


def expected_duration(tts_text: str) -> float:
    """duration_seconds formula from spec §5.4.2."""
    return max(5.0, char_count_chinese(tts_text) / 3.2 + 2.0)
