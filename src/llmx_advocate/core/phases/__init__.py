from llmx_advocate.core.engine import Phase
from llmx_advocate.core.models import PhaseId


def build_phase_registry() -> dict[PhaseId, Phase]:
    """Wire concrete phase implementations.

    V0.1 stubs return empty dicts and pass empty QA so the engine harness can be
    exercised end-to-end before phase business logic lands.
    """
    from llmx_advocate.core.phases.p1_5_angle import P1_5Angle
    from llmx_advocate.core.phases.p1_source_pack import P1SourcePack
    from llmx_advocate.core.phases.p2_5_judgment import P2_5Judgment
    from llmx_advocate.core.phases.p2_6_deepening import P2_6Deepening
    from llmx_advocate.core.phases.p2_layer import P2Layer
    from llmx_advocate.core.phases.p3_extract import P3Extract
    from llmx_advocate.core.phases.p4_video_json import P4VideoJSON
    from llmx_advocate.core.phases.p5_self_check import P5SelfCheck
    from llmx_advocate.core.phases.p6_publishing import P6Publishing

    return {
        PhaseId.P1: P1SourcePack(),
        PhaseId.P1_5: P1_5Angle(),
        PhaseId.P2: P2Layer(),
        PhaseId.P2_5: P2_5Judgment(),
        PhaseId.P2_6: P2_6Deepening(),
        PhaseId.P3: P3Extract(),
        PhaseId.P4: P4VideoJSON(),
        PhaseId.P5: P5SelfCheck(),
        PhaseId.P6: P6Publishing(),
    }
