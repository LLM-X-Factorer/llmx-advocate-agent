from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PhaseId(StrEnum):
    P1 = "P1"
    P1_5 = "P1.5"
    P2 = "P2"
    P2_5 = "P2.5"
    P2_6 = "P2.6"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"
    P0 = "P0"
    P7 = "P7"


class TaskStatus(StrEnum):
    RUNNING = "running"
    PAUSED_FOR_HUMAN = "paused_for_human"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseRunStatus(StrEnum):
    PASSED = "passed"
    QA_FAILED = "qa_failed"
    QA_FAILED_TERMINAL = "qa_failed_terminal"
    ERROR = "error"


class Tier(StrEnum):
    LIUYIN = "引流"
    LIUCUN = "留存"
    ZHUANHUA = "转化"


class Audience(StrEnum):
    STUDENT = "学生"
    PRACTITIONER = "从业者"
    DECISION_MAKER = "决策者"


class OpeningStyle(StrEnum):
    JUDGMENT_FIRST = "judgment_first"
    SUSPENSE_FIRST = "suspense_first"
    AUTO = "auto"


class ExportFormat(StrEnum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"


DEFAULT_RETRIES: dict[PhaseId, int] = {
    PhaseId.P1: 3,
    PhaseId.P1_5: 3,
    PhaseId.P2: 2,
    PhaseId.P2_5: 5,
    PhaseId.P2_6: 3,
    PhaseId.P3: 2,
    PhaseId.P4: 4,
    PhaseId.P5: 2,
    PhaseId.P6: 2,
    PhaseId.P0: 2,
    PhaseId.P7: 2,
}


# Source input — V0.1+ unified to a single source pack file (markdown + YAML frontmatter).
# See docs/source-pack-schema.md for the contract.
class SourceInput(BaseModel):
    pack_path: str | None = None       # local file path
    pack_content: str | None = None    # raw pack markdown — used when uploading via API


# === Source Pack frontmatter (matches docs/source-pack-schema.md §3) ===
class SourcePackSourceMeta(BaseModel):
    platform: Literal[
        "hacker_news", "github", "reddit", "x", "producthunt", "manual", "other"
    ]
    primary_url: str
    original_url: str | None = None
    title: str
    author: str | None = None
    published_at: datetime | None = None


class SourcePackMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    hn_score: int | None = None
    hn_comments: int | None = None
    github_stars: int | None = None
    github_stars_today: int | None = None
    reddit_upvotes: int | None = None
    reddit_comments: int | None = None
    x_likes: int | None = None
    x_replies: int | None = None


class ControversySignal(BaseModel):
    type: str
    evidence: str


class ScoutAnalysis(BaseModel):
    matched_keywords: list[str] = Field(default_factory=list)
    llm_score: float | None = None
    llm_reasoning: str | None = None
    judgment_seed: str | None = None
    suggested_layer: Tier | None = None
    controversy_signals: list[ControversySignal] = Field(default_factory=list)


class SourcePack(BaseModel):
    """Validated source pack — the contract between scout-agent and advocate-agent.

    Constructed by P1 from a frontmatter+body file. judgment_seed (if present) is a
    *gift* to P2.5, not a command — see spec §6 and prompts/p2_5_judgment/extract.md.
    """

    schema_version: Literal["1.0"]
    pack_id: str
    created_at: datetime
    created_by: str

    source: SourcePackSourceMeta
    metrics: SourcePackMetrics = Field(default_factory=SourcePackMetrics)
    scout_analysis: ScoutAnalysis | None = None

    body_markdown: str  # the full markdown body below the frontmatter


def _default_llm_provider() -> str:
    from llmx_advocate.settings import get_settings  # local import to avoid cycle
    return get_settings().llmx_default_provider


def _default_llm_model() -> str:
    from llmx_advocate.settings import get_settings
    return get_settings().llmx_default_model


class TaskConfig(BaseModel):
    target_audience: Audience = Audience.DECISION_MAKER
    target_tier: Tier | Literal["auto"] = "auto"
    export_formats: list[ExportFormat] | Literal["auto"] = "auto"
    opening_style: OpeningStyle = OpeningStyle.AUTO

    # Default to settings-derived values so env vars (e.g. LLMX_DEFAULT_PROVIDER) take effect
    # even when the caller doesn't explicitly set llm_provider / llm_model.
    llm_provider: str = Field(default_factory=_default_llm_provider)
    llm_model: str = Field(default_factory=_default_llm_model)

    qa_max_retries: dict[PhaseId, int] = Field(default_factory=lambda: DEFAULT_RETRIES.copy())

    enable_topic_validation: bool = False
    enable_commercial_alignment: bool = False
    enable_cognition_gap_check: bool = False


# Phase outputs (multi-shape, discriminated by phase_id at the PhaseRun level)


class Angle(BaseModel):
    hook_source: str
    core_tension: str
    your_position: str
    why_readers_care: str


class CharacteristicScores(BaseModel):
    data_impact: int = Field(ge=1, le=5)
    technical_depth: int = Field(ge=1, le=5)
    narrative_quality: int = Field(ge=1, le=5)
    timeliness: int = Field(ge=1, le=5)
    authority: int = Field(ge=1, le=5)
    decision_relevance: int = Field(ge=1, le=5)


class LayerProfile(BaseModel):
    tier: Tier
    characteristic_scores: CharacteristicScores
    target_duration_seconds: int
    target_scene_count: int
    export_formats: list[ExportFormat]


class Judgment(BaseModel):
    surface: str
    transition: str
    deeper_essence: str
    full_sentence: str

    # Override semantics — see spec §5.1 / docs/source-pack-schema.md §5.
    # If the source pack provided a judgment_seed and we kept it: overrode_seed=False, seed_judgment=<that string>.
    # If we replaced the seed with our own judgment: overrode_seed=True + override_reason explains why.
    # If no seed existed (manual pack or scout had none): seed_judgment=None, overrode_seed=False.
    seed_judgment: str | None = None
    overrode_seed: bool = False
    override_reason: str | None = None


class DeepThinking(BaseModel):
    """Output of P2.6 — three-layer deep thinking + the validated theme.

    `theme` is the one-sentence statement P2.6 finalises after the why/meaning
    rounds. It must be at least as deep as the P2.5 judgment (often the same
    sentence, sometimes refined). Downstream phases (P3+) consume `theme` as
    the unifying claim of the video.
    """

    why_round: list[str]
    meaning_round: list[str]
    validation_notes: str
    theme: str


class Finding(BaseModel):
    description: str
    key_data: str | None = None
    source: str | None = None


class Story(BaseModel):
    title: str
    summary: str


class CoreInfo(BaseModel):
    """P3 output — extracted material organised by the 5 richness dimensions.

    The dbs-hook material check (spec §5.6) requires at least 3 of 5 dimensions
    to be non-empty: data / story / quote / authority / pain. Dimensions other
    than findings default to empty so the gate logic can count actual coverage.
    """

    findings: list[Finding] = Field(min_length=3, max_length=5)
    key_data_points: list[str] = Field(default_factory=list)
    stories: list[Story] = Field(default_factory=list)
    quotable_lines: list[str] = Field(default_factory=list)
    authority_anchors: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    advocate_interpretation: str


# Video JSON aligns with VIDEO_JSON_REFERENCE.md schema. We keep it as a generic dict here
# and validate via jsonschema (the canonical schema lives in core/schemas/video_json.json).
class VideoJSON(BaseModel):
    model_config = ConfigDict(extra="allow")

    export_formats: list[ExportFormat] = Field(default_factory=lambda: [ExportFormat.LANDSCAPE])
    scenes: list[dict[str, Any]]


class ValidationReport(BaseModel):
    syntax_ok: bool
    sync_warnings: list[str] = Field(default_factory=list)
    duration_total: int
    tts_total_chars: int
    scene_type_distribution: dict[str, int] = Field(default_factory=dict)


class TitleOption(BaseModel):
    text: str
    formula_id: str | None = None
    rationale: str | None = None


class Publishing(BaseModel):
    titles: list[TitleOption] = Field(min_length=2, max_length=3)
    description: str
    pinned_comment: str | None = None


PhaseOutput = Annotated[
    SourcePack | Angle | LayerProfile | Judgment | DeepThinking | CoreInfo | VideoJSON | ValidationReport | Publishing,
    Field(discriminator=None),
]


# QA
class QAGate(BaseModel):
    gate_id: str
    name: str
    passed: bool
    rationale: str
    evidence: Any | None = None


class QAResult(BaseModel):
    gates: list[QAGate]
    passed_overall: bool


# Cost / usage
class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_cost_usd: float = 0.0


# Persistence-facing aggregates
class Task(BaseModel):
    id: str
    title: str
    source: SourceInput
    config: TaskConfig
    current_phase: PhaseId = PhaseId.P1
    status: TaskStatus = TaskStatus.RUNNING
    created_at: datetime
    updated_at: datetime


class PhaseRun(BaseModel):
    id: str
    task_id: str
    phase_id: PhaseId
    attempt: int = 1
    trigger: Literal["auto", "manual_resume", "manual_qa_rerun"] = "auto"

    llm_provider: str
    llm_model: str

    output: dict[str, Any]
    qa_result: QAResult | None = None
    status: PhaseRunStatus

    edited_by_human: bool = False
    edit_note: str | None = None

    cost: TokenUsage = Field(default_factory=TokenUsage)
    duration_ms: int = 0

    started_at: datetime
    finished_at: datetime | None = None


class HumanEdit(BaseModel):
    id: str
    task_id: str
    phase_id: PhaseId
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str
    edited_at: datetime
