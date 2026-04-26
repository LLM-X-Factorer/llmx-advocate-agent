from llmx_advocate.core.models import (
    DEFAULT_RETRIES,
    OpeningStyle,
    PhaseId,
    SourceInput,
    TaskConfig,
)


def test_default_retries_cover_all_required_phases():
    for phase in (PhaseId.P1, PhaseId.P1_5, PhaseId.P2, PhaseId.P2_5, PhaseId.P3, PhaseId.P4, PhaseId.P5, PhaseId.P6):
        assert phase in DEFAULT_RETRIES


def test_p2_5_gets_more_retries_than_p5():
    assert DEFAULT_RETRIES[PhaseId.P2_5] > DEFAULT_RETRIES[PhaseId.P5]


def test_taskconfig_defaults():
    cfg = TaskConfig()
    assert cfg.opening_style == OpeningStyle.AUTO
    assert cfg.enable_topic_validation is False
    assert cfg.enable_commercial_alignment is False
    # llm_provider/llm_model defaults are settings-derived; test they're non-empty.
    assert cfg.llm_provider in ("anthropic", "openrouter")
    assert cfg.llm_model


def test_source_input_pack_path():
    s = SourceInput(pack_path="/some/path/pack.md")
    assert s.pack_path == "/some/path/pack.md"
    assert s.pack_content is None


def test_source_input_pack_content():
    s = SourceInput(pack_content="---\nfoo: bar\n---\nbody")
    assert s.pack_content is not None
    assert s.pack_path is None
