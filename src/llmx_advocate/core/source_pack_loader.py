"""Source pack file parser & validator.

Contract: docs/source-pack-schema.md.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from llmx_advocate.core.models import SourcePack


class InvalidSourcePackError(ValueError):
    """Raised when a pack file fails schema validation."""


FRONTMATTER_DELIMITER = "---"


def split_frontmatter(text: str) -> tuple[str, str]:
    """Returns (frontmatter_yaml, body_markdown).

    Raises InvalidSourcePackError if no frontmatter block is present.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise InvalidSourcePackError("missing leading '---' frontmatter delimiter")

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIMITER:
            end_idx = i
            break

    if end_idx is None:
        raise InvalidSourcePackError("frontmatter not closed by '---'")

    frontmatter = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    return frontmatter, body


def parse(text: str) -> SourcePack:
    """Parse a markdown+frontmatter source pack into a validated SourcePack."""
    fm_text, body = split_frontmatter(text)

    try:
        fm_data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise InvalidSourcePackError(f"YAML parse error in frontmatter: {e}") from e

    if not isinstance(fm_data, dict):
        raise InvalidSourcePackError("frontmatter must be a YAML mapping")

    fm_data["body_markdown"] = body

    try:
        return SourcePack.model_validate(fm_data)
    except ValidationError as e:
        raise InvalidSourcePackError(f"schema validation failed:\n{e}") from e


def parse_file(path: str | Path) -> SourcePack:
    p = Path(path)
    if not p.is_file():
        raise InvalidSourcePackError(f"pack file not found: {p}")
    return parse(p.read_text(encoding="utf-8"))


# Markdown body section classification — see docs/source-pack-schema.md
# §"Markdown body 段落约定". Hint sections contain scout's pre-judgement and
# metadata for human readers; source sections contain the actual upstream
# content. Downstream uniqueness / relay checks must only see source sections,
# otherwise a judgment that legitimately deepens scout's seed gets flagged as
# "duplicating the original" because the seed itself is in the body.
HINT_SECTION_TITLES = frozenset({
    "来源元信息",
    "Scout 的预判",
})

SOURCE_SECTION_TITLES = frozenset({
    "原文正文",
    "评论区精华",
    "相关讨论",
})


def extract_source_sections(body_markdown: str) -> str:
    """Return only the *source* portions of a scout-rendered body.

    Splits the body on `## ` headings and keeps sections whose title appears in
    `SOURCE_SECTION_TITLES` (per the schema's body convention). Leading content
    above the first `## ` heading (e.g. the H1 title) is preserved as
    factual context — this matches what a human would consider "the upstream
    document" minus scout's annotations.

    For manual packs that don't follow the convention (no `##` headings at
    all, or no recognisable source sections), the full body is returned —
    we'd rather over-include than starve the uniqueness check on hand-written
    inputs.
    """
    if not body_markdown.strip():
        return body_markdown

    lines = body_markdown.splitlines(keepends=True)
    parts: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in lines:
        if line.startswith("## "):
            heading = line[3:].rstrip().rstrip("\n").strip()
            parts.append((heading, [line]))
        else:
            parts[-1][1].append(line)

    has_recognised_source = any(
        h in SOURCE_SECTION_TITLES for h, _ in parts if h is not None
    )

    keep: list[str] = []
    for heading, content in parts:
        if heading is None:
            keep.extend(content)
        elif heading in HINT_SECTION_TITLES:
            continue
        elif heading in SOURCE_SECTION_TITLES:
            keep.extend(content)
        else:
            # Unknown ## heading — keep it. Pack authors may add custom sections.
            keep.extend(content)

    if not has_recognised_source:
        return body_markdown

    return "".join(keep).rstrip() + "\n"
