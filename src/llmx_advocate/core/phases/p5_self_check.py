from llmx_advocate.core.models import PhaseId
from llmx_advocate.core.phases._base import StubPhase


class P5SelfCheck(StubPhase):
    """Video JSON self-check.

    QA layers (spec §5.4 / §5.5):
      - JSON Schema validation (rule)
      - Duration formula validation (rule)
      - 6 TTS-Visual sync rules (rule + judge)
      - Anti-AI smell (rule + judge)
      - Structural completeness (cover→hook→channel_intro→...→outro)

    On retry exhaustion → fallback to P4 (regenerate JSON).
    """

    phase_id = PhaseId.P5
    fallback_target = PhaseId.P4
