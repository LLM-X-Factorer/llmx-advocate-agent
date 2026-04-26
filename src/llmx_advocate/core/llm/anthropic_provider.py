from __future__ import annotations

from anthropic import AsyncAnthropic

from llmx_advocate.core.llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    maybe_parse_json,
)
from llmx_advocate.core.models import TokenUsage
from llmx_advocate.settings import get_settings


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(self, req: LLMRequest) -> LLMResponse:
        kwargs: dict = {
            "model": req.model,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "messages": req.messages,
        }
        if req.system:
            kwargs["system"] = req.system

        message = await self.client.messages.create(**kwargs)

        text_blocks = [b.text for b in message.content if getattr(b, "type", "") == "text"]
        text = "\n".join(text_blocks)

        usage = TokenUsage(
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

        parsed = maybe_parse_json(text) if req.response_format == "json" else None

        return LLMResponse(text=text, usage=usage, parsed_json=parsed, raw=message)
