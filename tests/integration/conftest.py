from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from llmx_advocate.core.llm.provider import LLMResponse
from llmx_advocate.core.models import TokenUsage
from llmx_advocate.store.db import Base


@pytest.fixture
async def db_session() -> AsyncIterator:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Mock all LLM provider calls in integration tests.

    Without this, phases that invoke LLMs (P1.5+) would either hit the network
    or fail on missing API keys. Each test still controls behaviour by overriding
    the returned response via monkeypatch on specific module paths if needed.
    """
    angle_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        parsed_json={
            "hook_source": "HN top comment",
            "core_tension": "RAG dead vs not dead",
            "your_position": "real shift is iterative retrieval",
            "why_readers_care": "anyone shipping retrieval is affected",
        },
    )
    layer_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=200, output_tokens=80),
        parsed_json={
            "tier": "留存",
            "characteristic_scores": {
                "data_impact": 4,
                "technical_depth": 3,
                "narrative_quality": 4,
                "timeliness": 5,
                "authority": 5,
                "decision_relevance": 5,
            },
            "target_duration_seconds": 600,
            "target_scene_count": 24,
            "export_formats": ["landscape"],
        },
    )
    judgment_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=400, output_tokens=120),
        parsed_json={
            "surface": "RAG 被 agent 取代",
            "transition": "但其实",
            "deeper_essence": "检索范式从一次性到迭代",
            "full_sentence": "RAG 没有死，它从主角变成了 agent 的工具",
            "seed_judgment": None,
            "overrode_seed": False,
            "override_reason": None,
        },
    )
    judge_response = LLMResponse(
        text='{"passed": true, "rationale": "ok"}',
        usage=TokenUsage(input_tokens=80, output_tokens=20),
        parsed_json={"passed": True, "rationale": "ok"},
    )

    angle_provider = AsyncMock()
    angle_provider.complete = AsyncMock(return_value=angle_response)
    layer_provider = AsyncMock()
    layer_provider.complete = AsyncMock(return_value=layer_response)
    judgment_provider = AsyncMock()
    judgment_provider.complete = AsyncMock(return_value=judgment_response)
    judge_provider = AsyncMock()
    judge_provider.complete = AsyncMock(return_value=judge_response)

    monkeypatch.setattr(
        "llmx_advocate.core.phases.p1_5_angle.get_provider",
        lambda _: angle_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_layer.get_provider",
        lambda _: layer_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p2_5_judgment.get_provider",
        lambda _: judgment_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.qa.judges.get_judge_provider",
        lambda: judge_provider,
    )
