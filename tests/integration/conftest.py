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
            "seed_relation": "none",
            "override_reason": None,
        },
    )
    deepening_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=300, output_tokens=200),
        parsed_json={
            "why_round": ["为什么1：单次召回受限", "为什么2：agent 拆成多步"],
            "meaning_round": ["对开发：放弃一次到位执念", "对评测：静态 benchmark 失真"],
            "validation_notes": "三轮追问后判断仍成立",
            "theme": "检索范式从静态召回转向迭代探索",
        },
    )
    extract_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=500, output_tokens=400),
        parsed_json={
            "findings": [
                {"description": "发现1", "key_data": "55%", "source": "原文"},
                {"description": "发现2", "key_data": "1.3 月", "source": "原文"},
                {"description": "发现3", "key_data": "920x", "source": "原文"},
            ],
            "key_data_points": ["460 万美元 — 模拟环境总价值"],
            "stories": [{"title": "四天时间差", "summary": "AI 早于人类黑客四天"}],
            "quotable_lines": ["从复现到发现"],
            "authority_anchors": ["Anthropic 红队报告"],
            "pain_points": ["工程师不理解 agent 安全边界"],
            "advocate_interpretation": "三个信号 + 三点建议",
        },
    )

    # Build a video JSON that satisfies P4 + P5 gates against the mock LayerProfile
    # (tier=留存, target_duration=600s, target_scene_count=24). Avoid 第一/第二/第三
    # enumeration here so P5_no_mechanical_enumeration stays under the 2-group cap.
    def _video_scenes() -> list[dict]:
        from llmx_advocate.core.qa.rules import expected_duration
        long_tts = (
            "这一段我们讲核心发现。数据支撑这个观点的具体含义在于哪里？"
            "可以从规模、趋势与现实启示这几个角度切入，把背后的逻辑铺开。"
            "每个角度都对从业者有现实意义，值得展开来讲清楚。"
        )
        scenes = [
            {"scene_type": "cover", "title": "封面", "duration_seconds": 3},
            {
                "scene_type": "hook",
                "main_text": "很多人觉得 RAG 已经死了，但其实检索范式从静态到动态。",
                "tts_text": "很多人觉得 RAG 已经死了，但其实检索范式从静态到动态，从一次性召回转向迭代探索。这一点值得深入。",
                "duration_seconds": round(expected_duration("很多人觉得 RAG 已经死了，但其实检索范式从静态到动态，从一次性召回转向迭代探索。这一点值得深入。"), 1),
            },
            {
                "scene_type": "channel_intro",
                "main_text": "LLM-X-Factors",
                "tts_text": "大家好，这里是LLM-X-Factors，一个专注于拆解大语言模型时代底层逻辑的频道。",
                "duration_seconds": round(expected_duration("大家好，这里是LLM-X-Factors，一个专注于拆解大语言模型时代底层逻辑的频道。"), 1),
            },
            {
                "scene_type": "hook_support",
                "title": "数据支撑",
                "tts_text": "我们来看一下数据。某项基准 55%，另外能力 1.3 月翻倍，规模化扫描成本降到 1.22 美元。这些数字告诉我们一件事：从复现到发现。",
                "duration_seconds": round(expected_duration("我们来看一下数据。某项基准 55%，另外能力 1.3 月翻倍，规模化扫描成本降到 1.22 美元。这些数字告诉我们一件事：从复现到发现。"), 1),
            },
        ]
        for i in range(19):
            if i % 5 == 0:
                tts = "我们继续看下一段。"
                scenes.append({
                    "scene_type": "chapter_transition",
                    "chapter_number": f"{i // 5 + 1:02d}",
                    "chapter_title": f"第 {i // 5 + 1} 章",
                    "tts_text": tts,
                    "duration_seconds": round(expected_duration(tts), 1),
                })
            else:
                scenes.append({
                    "scene_type": "content",
                    "title": f"第 {i} 点",
                    "bullets": ["要点1", "要点2"],
                    "tts_text": long_tts,
                    "duration_seconds": round(expected_duration(long_tts), 1),
                })
        scenes.append({
            "scene_type": "outro",
            "headline": "我们下期见",
            "tts_text": "这里是LLM-X-Factors，我们下期见。",
            "duration_seconds": round(expected_duration("这里是LLM-X-Factors，我们下期见。"), 1),
        })
        return scenes

    video_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=2000, output_tokens=2500),
        parsed_json={"export_formats": ["landscape"], "scenes": _video_scenes()},
    )
    publishing_response = LLMResponse(
        text="",
        usage=TokenUsage(input_tokens=600, output_tokens=400),
        parsed_json={
            "titles": [
                {
                    "text": "为什么 90% 的 RAG 项目都活不过 demo？",
                    "formula_id": "liucun_essence",
                    "rationale": "点出 RAG 失败的本质原因",
                },
                {
                    "text": "RAG 没死：检索范式从静态到动态的演进",
                    "formula_id": "liucun_judgment",
                    "rationale": "呈现核心判断",
                },
            ],
            "description": (
                "📊 检索范式正在悄悄演进。本期我们拆解 3 个数据信号，"
                "看为什么 RAG 没有被取代，而是变成 agent 的工具。"
                "🔍 案例：Anthropic 红队报告里的关键转折。"
                "💡 洞察：从一次性召回到迭代探索。"
                "💬 你怎么看？欢迎讨论。"
            ),
            "pinned_comment": (
                "⏱️ 时间戳：\n"
                "00:00 开场\n"
                "01:30 章节 1：数据现实\n"
                "05:00 章节 2：范式转移\n"
                "08:00 章节 3：对开发者的影响\n"
                "💬 看完有什么想法？"
            ),
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
    deepening_provider = AsyncMock()
    deepening_provider.complete = AsyncMock(return_value=deepening_response)
    extract_provider = AsyncMock()
    extract_provider.complete = AsyncMock(return_value=extract_response)
    video_provider = AsyncMock()
    video_provider.complete = AsyncMock(return_value=video_response)
    publishing_provider = AsyncMock()
    publishing_provider.complete = AsyncMock(return_value=publishing_response)
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
        "llmx_advocate.core.phases.p2_6_deepening.get_provider",
        lambda _: deepening_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p3_extract.get_provider",
        lambda _: extract_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p4_video_json.get_provider",
        lambda _: video_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.phases.p6_publishing.get_provider",
        lambda _: publishing_provider,
    )
    monkeypatch.setattr(
        "llmx_advocate.core.qa.judges.get_judge_provider",
        lambda: judge_provider,
    )
