"""Judge-LLM wrappers.

The judge model is FIXED at the engine layer (see settings.llmx_judge_*) so QA semantics
do not drift when generation-side LLM changes. Do not parameterise this from TaskConfig.
"""

from __future__ import annotations

import re

from llmx_advocate.core.llm.provider import LLMRequest, get_judge_provider
from llmx_advocate.core.prompts import read_raw, render_string
from llmx_advocate.settings import get_settings

JUDGE_SYSTEM = (
    "You are a strict, binary judge for content-quality gates. "
    'Reply ONLY in JSON: {"passed": bool, "rationale": string}. '
    "Be precise and skeptical. The cost of a false-positive (passing bad content) is much higher "
    "than a false-negative (failing borderline content)."
)


async def judge(prompt: str) -> dict:
    """Run a single judge call. Returns {"passed": bool, "rationale": str}."""
    settings = get_settings()
    provider = get_judge_provider()
    response = await provider.complete(
        LLMRequest(
            model=settings.llmx_judge_model,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            response_format="json",
            temperature=0.0,
            # 800 instead of 300 — reasoning judge models (e.g. deepseek-v4-pro)
            # spend most of their budget on internal reasoning before emitting
            # JSON; tight caps caused truncated bodies and false unparsable hits.
            max_tokens=800,
        )
    )
    parsed = response.parsed_json or {"passed": False, "rationale": "judge response unparsable"}
    if "passed" not in parsed:
        return {"passed": False, "rationale": f"judge returned no 'passed' key: {response.text[:120]}"}
    return parsed


async def judge_with_template(template_ref: str, **context) -> dict:
    """Run a judge gate defined in a markdown template file.

    template_ref format: 'p1_5_angle/judges.md#GATE_ID'.
    The named section under '## GATE_ID' in the file is extracted, rendered with
    Jinja2 context, and submitted as the judge prompt.
    """
    if "#" not in template_ref:
        raise ValueError(f"template_ref must include '#GATE_ID': {template_ref!r}")
    file_path, gate_id = template_ref.split("#", 1)

    # Extract the section *first*, then render — otherwise Jinja must satisfy variables
    # for every gate in the file even when we only target one.
    raw_md = read_raw(file_path)
    section_template = _extract_judge_section(raw_md, gate_id)
    rendered = render_string(section_template, **context)
    return await judge(rendered)


def _extract_judge_section(markdown: str, gate_id: str) -> str:
    """Extract content of '## {gate_id}' section, stripping ``` fences if present."""
    pattern = rf"^##\s+{re.escape(gate_id)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, markdown, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"gate section '## {gate_id}' not found in template")

    section = match.group(1).strip()
    fence_match = re.search(r"```\s*\n(.*?)\n```", section, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return section
