from llmx_advocate.core.models import PhaseId
from llmx_advocate.core.phases._base import StubPhase


class P6Publishing(StubPhase):
    phase_id = PhaseId.P6
    fallback_target = None
