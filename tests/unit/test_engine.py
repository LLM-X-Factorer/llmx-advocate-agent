from llmx_advocate.core.engine import FALLBACK_TABLE, PHASE_ORDER, PhaseEngine
from llmx_advocate.core.models import PhaseId


def test_phase_order_is_linear_and_complete():
    assert PHASE_ORDER[0] == PhaseId.P1
    assert PHASE_ORDER[-1] == PhaseId.P6
    assert len(set(PHASE_ORDER)) == len(PHASE_ORDER)


def test_fallback_table_matches_spec():
    assert FALLBACK_TABLE[PhaseId.P1_5] == PhaseId.P1
    assert FALLBACK_TABLE[PhaseId.P2_5] == PhaseId.P1_5
    assert FALLBACK_TABLE[PhaseId.P2_6] == PhaseId.P2_5
    assert FALLBACK_TABLE[PhaseId.P5] == PhaseId.P4


def test_engine_next_phase():
    engine = PhaseEngine(phases={})
    assert engine.next_phase(PhaseId.P1) == PhaseId.P1_5
    assert engine.next_phase(PhaseId.P5) == PhaseId.P6
    assert engine.next_phase(PhaseId.P6) is None
