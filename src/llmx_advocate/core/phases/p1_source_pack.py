from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.models import PhaseId, QAGate, QAResult
from llmx_advocate.core.source_pack_loader import (
    InvalidSourcePackError,
    parse,
    parse_file,
)

MIN_BODY_CHARS = 100


class P1SourcePack(Phase):
    """P1 — Source Pack Loading & Validation.

    Reads a SourcePack from TaskContext.task.source (pack_path or pack_content),
    validates against schema v1.0, returns the serialised pack as PhaseOutput.

    Failures here mean the input file is broken — the engine fails the task fast
    instead of retrying (retries don't fix bad data).
    """

    phase_id = PhaseId.P1
    fallback_target = None

    async def run(self, ctx: TaskContext) -> dict:
        src = ctx.task.source
        if src.pack_path:
            pack = parse_file(src.pack_path)
        elif src.pack_content:
            pack = parse(src.pack_content)
        else:
            raise InvalidSourcePackError("SourceInput must set either pack_path or pack_content")
        return pack.model_dump(mode="json")

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        gates: list[QAGate] = [
            _gate_body_non_empty(output),
            _gate_body_min_length(output),
            _gate_has_section_header(output),
        ]
        return QAResult(gates=gates, passed_overall=all(g.passed for g in gates))


def _gate_body_non_empty(output: dict) -> QAGate:
    body = output.get("body_markdown", "")
    passed = bool(body and body.strip())
    return QAGate(
        gate_id="P1_body_non_empty",
        name="body 非空",
        passed=passed,
        rationale="body_markdown is empty after stripping" if not passed else "ok",
    )


def _gate_body_min_length(output: dict) -> QAGate:
    body = output.get("body_markdown", "")
    char_count = len(body.strip())
    passed = char_count >= MIN_BODY_CHARS
    return QAGate(
        gate_id="P1_body_min_length",
        name=f"body 长度 ≥ {MIN_BODY_CHARS} 字符",
        passed=passed,
        rationale=f"body has {char_count} chars" if not passed else "ok",
        evidence={"char_count": char_count} if not passed else None,
    )


def _gate_has_section_header(output: dict) -> QAGate:
    body: str = output.get("body_markdown", "")
    passed = any(line.startswith(("# ", "## ", "### ")) for line in body.splitlines())
    return QAGate(
        gate_id="P1_has_section_header",
        name="body 至少有一个 markdown 标题",
        passed=passed,
        rationale="no '# ' / '## ' / '### ' header found in body" if not passed else "ok",
    )
