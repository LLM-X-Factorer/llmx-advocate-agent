from llmx_advocate.core.models import PhaseId
from llmx_advocate.core.phases._base import StubPhase


class P2_6Deepening(StubPhase):
    phase_id = PhaseId.P2_6
    fallback_target = PhaseId.P2_5
