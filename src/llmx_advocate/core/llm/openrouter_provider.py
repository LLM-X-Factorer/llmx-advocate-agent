from __future__ import annotations

import httpx

from llmx_advocate.core.llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    maybe_parse_json,
)
from llmx_advocate.core.models import TokenUsage
from llmx_advocate.settings import get_settings

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openrouter_api_key

    async def complete(self, req: LLMRequest) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/LLM-X-Factorer/llmx-advocate-agent",
            "X-Title": "llmx-advocate-agent",
        }
        messages: list[dict] = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.extend(req.messages)

        body = {
            "model": req.model,
            "messages": messages,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if req.response_format == "json":
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            r = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()

        choice = data["choices"][0]
        text = choice["message"]["content"] or ""

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )

        parsed = maybe_parse_json(text) if req.response_format == "json" else None

        return LLMResponse(text=text, usage=usage, parsed_json=parsed, raw=data)
