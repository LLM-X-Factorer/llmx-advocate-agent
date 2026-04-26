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

# Status codes that warrant automatic retry (transient upstream issues).
# 429: rate limit. 502/503/504: gateway / upstream provider hiccups (SiliconFlow,
# DeepSeek's hosting layer, etc. — common with reasoning-heavy long prompts).
RETRYABLE_STATUS = {429, 502, 503, 504}


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
        # Note: we deliberately do NOT pass response_format={"type":"json_object"} to
        # OpenRouter — many of its endpoint providers (incl. SiliconFlow / DeepSeek
        # routes) reject this with a 404 "guardrail restrictions" error. We rely on
        # prompt-level JSON instructions and core/phases/p1_5_angle._extract_first_json_object
        # to salvage from fenced or prose-wrapped responses.

        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            for attempt in range(RATE_LIMIT_RETRIES + 1):
                r = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=body
                )

                # 200 with an error envelope (e.g. {"error": {"code": 504, ...}})
                # — also treat as a retryable upstream hiccup, not a permanent failure.
                upstream_err_code: int | None = None
                if r.status_code == 200:
                    try:
                        body_json = r.json()
                        if "choices" not in body_json:
                            err = body_json.get("error") or {}
                            upstream_err_code = int(err.get("code")) if err.get("code") else None
                    except (ValueError, httpx.DecodingError):
                        pass

                http_retryable = r.status_code in RETRYABLE_STATUS
                envelope_retryable = upstream_err_code in RETRYABLE_STATUS

                if (http_retryable or envelope_retryable) and attempt < RATE_LIMIT_RETRIES:
                    wait_s = float(
                        r.headers.get(
                            "Retry-After", RATE_LIMIT_BACKOFF_BASE_S * 2 ** attempt
                        )
                    )
                    await asyncio.sleep(min(wait_s, 30.0))
                    continue

                r.raise_for_status()
                break

            data = r.json()

        # OpenRouter sometimes returns 200 with a body that has 'error' instead of 'choices'
        # (e.g. SiliconFlow guardrails / non-retryable refusals). Surface this clearly
        # rather than letting a KeyError mask the actual API message.
        if "choices" not in data:
            err = data.get("error") or data
            raise RuntimeError(f"OpenRouter returned non-completion body: {err}")

        choice = data["choices"][0]
        text = choice["message"]["content"] or ""

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )

        parsed = maybe_parse_json(text) if req.response_format == "json" else None

        return LLMResponse(text=text, usage=usage, parsed_json=parsed, raw=data)
