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
