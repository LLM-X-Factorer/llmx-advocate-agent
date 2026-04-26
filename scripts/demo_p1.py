"""Demo: run a task through P1 in-memory, stop when next stub phase raises.

Usage:
    python scripts/demo_p1.py                       # uses bundled scout fixture
    python scripts/demo_p1.py path/to/pack.md       # use your own pack

This is a debugging tool, NOT the production task runner. It bypasses DB / worker
to show the engine + P1 contract working end-to-end.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from llmx_advocate.core.engine import PHASE_ORDER, TaskContext
from llmx_advocate.core.models import (
    PhaseId,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
)
from llmx_advocate.core.phases import build_phase_registry

DEFAULT_PACK = (
    Path(__file__).parent.parent / "tests" / "fixtures" / "example-pack" / "scout-pack-example.md"
)


async def demo(pack_path: Path) -> None:
    print(f"==> Loading pack: {pack_path}")
    print()

    task = Task(
        id="DEMO0001",
        title=f"demo {pack_path.name}",
        source=SourceInput(pack_path=str(pack_path)),
        config=TaskConfig(),
        current_phase=PhaseId.P1,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    phases = build_phase_registry()
    ctx = TaskContext(task=task, upstream_outputs={})

    for phase_id in PHASE_ORDER:
        phase = phases[phase_id]
        print(f"--- {phase_id} {phase.__class__.__name__} ---")
        try:
            output = await phase.run(ctx)
        except NotImplementedError as e:
            print(f"  [stop] stub phase not yet implemented: {e}")
            break

        ctx.upstream_outputs[phase_id] = output
        print(f"  run output keys: {sorted(output.keys())[:8]}")

        qa = await phase.qa(output, ctx)
        print(f"  qa.passed_overall = {qa.passed_overall}")
        for g in qa.gates:
            mark = "OK " if g.passed else "FAIL"
            print(f"    [{mark}] {g.gate_id:30s} {g.rationale}")

        if not qa.passed_overall:
            print(f"  [stop] phase {phase_id} QA failed — engine would retry / fallback here")
            break

        print()

    print()
    print("==> Demo end. PhaseRun records that would be persisted:")
    print(json.dumps(list(ctx.upstream_outputs.keys()), default=str))


def main() -> None:
    pack_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PACK
    if not pack_path.is_file():
        print(f"Pack file not found: {pack_path}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(demo(pack_path))


if __name__ == "__main__":
    main()
