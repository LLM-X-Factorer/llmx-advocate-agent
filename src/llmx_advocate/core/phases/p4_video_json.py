from llmx_advocate.core.models import PhaseId
from llmx_advocate.core.phases._base import StubPhase


class P4VideoJSON(StubPhase):
    """Video JSON generation — opening self-check forks by TaskConfig.opening_style.

    Common red lines (spec §5.3.0): no source-backing, no relay, no pan-KOL openings,
    first sentence must be complete, judgment must exist, must be oral-friendly.

    judgment_first style (§5.3.1): judgment within 15s, before channel_intro.
    suspense_first style (§5.3.2): topic established in 5s, hook strength, credibility,
    no answer leak in first 30s, judgment lands at 30-60s.
    """

    phase_id = PhaseId.P4
    fallback_target = None
