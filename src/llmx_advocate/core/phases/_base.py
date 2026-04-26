from __future__ import annotations

from llmx_advocate.core.engine import Phase, TaskContext
from llmx_advocate.core.models import PhaseId, QAResult


class StubPhase(Phase):
    """Default skeleton — concrete phases override `run` and `qa`.

    Calling .run on a stub raises NotImplementedError so the engine never silently
    produces empty content. The CLI / API surface stays usable; phase business is
    filled in incrementally per spec.
    """

    phase_id: PhaseId
    fallback_target: PhaseId | None = None

    async def run(self, ctx: TaskContext) -> dict:
        raise NotImplementedError(f"{self.phase_id} business logic not yet implemented")

    async def qa(self, output: dict, ctx: TaskContext) -> QAResult:
        return QAResult(gates=[], passed_overall=True)
