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
