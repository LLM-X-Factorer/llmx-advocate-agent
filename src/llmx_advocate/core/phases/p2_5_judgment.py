from llmx_advocate.core.models import PhaseId
from llmx_advocate.core.phases._base import StubPhase


class P2_5Judgment(StubPhase):
    """Core judgment extraction — the spec's most critical phase.

    QA gates (spec §5.1):
      P2.5_uniqueness          (judge)
      P2.5_independent_value   (judge)
      P2.5_brevity             (rule, ≤50 chars)
      P2.5_anti_relay          (rule + judge)
      P2.5_cognition_gap       (judge, optional)

    On retry exhaustion → fallback to P1.5 (角度换).
    """

    phase_id = PhaseId.P2_5
    fallback_target = PhaseId.P1_5
