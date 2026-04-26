from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(PROMPTS_DIR),
        autoescape=select_autoescape(default=False, default_for_string=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render(template_path: str, **context) -> str:
    """Render a prompt template by path, e.g. 'p1_5_angle/extract.md'."""
    return _env().get_template(template_path).render(**context)


def render_string(template_string: str, **context) -> str:
    """Render an inline Jinja2 string with the same env settings."""
    return _env().from_string(template_string).render(**context)


def read_raw(template_path: str) -> str:
    """Read a prompt file as raw text (no rendering)."""
    return (PROMPTS_DIR / template_path).read_text(encoding="utf-8")
