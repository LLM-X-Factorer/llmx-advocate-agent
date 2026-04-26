from __future__ import annotations

import asyncio

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
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_BASE_S = 2.0


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
            for attempt in range(RATE_LIMIT_RETRIES + 1):
                r = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=body
                )
                if r.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
                    r.raise_for_status()
                    break
                # Honor Retry-After if present, else exponential backoff.
                wait_s = float(r.headers.get("Retry-After", RATE_LIMIT_BACKOFF_BASE_S * 2 ** attempt))
                await asyncio.sleep(min(wait_s, 30.0))
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
