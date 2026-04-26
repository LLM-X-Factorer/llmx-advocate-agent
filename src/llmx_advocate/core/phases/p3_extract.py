from llmx_advocate.core.models import PhaseId
from llmx_advocate.core.phases._base import StubPhase


class P3Extract(StubPhase):
    """Core information extraction.

    QA gates (spec §5.6):
      P3_material_richness  — must hit ≥3 of 5 dims (data/story/quote/authority/pain)
      P3_topic_breadth      — audience width check
    """

    phase_id = PhaseId.P3
    fallback_target = None
