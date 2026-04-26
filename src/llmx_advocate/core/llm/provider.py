from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from llmx_advocate.core.models import TokenUsage
from llmx_advocate.settings import get_settings


@dataclass
class LLMRequest:
    model: str
    messages: list[dict[str, Any]]
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    response_format: Literal["text", "json"] = "text"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    usage: TokenUsage
    parsed_json: dict | None = None
    raw: Any = None


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, req: LLMRequest) -> LLMResponse:
        raise NotImplementedError


def get_provider(provider_name: str) -> LLMProvider:
    if provider_name == "anthropic":
        from llmx_advocate.core.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if provider_name == "openrouter":
        from llmx_advocate.core.llm.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider()
    raise ValueError(f"Unknown LLM provider: {provider_name}")


def get_judge_provider() -> LLMProvider:
    """Always returns the FIXED judge provider regardless of TaskConfig."""
    settings = get_settings()
    return get_provider(settings.llmx_judge_provider)


def maybe_parse_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
