"""Verify LLM provider abstraction with real API calls.

Usage:
    python scripts/verify_llm.py --check-only            # check env, no API calls (free)
    python scripts/verify_llm.py --execute               # real API calls (costs money)
    python scripts/verify_llm.py --execute \
      --anthropic-model claude-opus-4-5 \
      --openrouter-model deepseek/deepseek-r1 \
      --prompt "Explain in one sentence what RAG is"

Why this exists: before wiring phases that depend on LLM, prove the provider
abstraction round-trips correctly with both backends. Also exposes API key
issues / model name mismatches early.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass

from llmx_advocate.core.llm.provider import LLMRequest, get_provider
from llmx_advocate.settings import get_settings

DEFAULT_PROMPT = "用一句话（不超过 30 字）解释什么是 RAG。"


@dataclass
class Result:
    provider: str
    model: str
    ok: bool
    duration_s: float
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""


def check_env(providers: list[str]) -> tuple[bool, list[str]]:
    """Check only the requested providers' keys. Returns (all_ok, messages)."""
    settings = get_settings()
    msgs = []
    ok = True

    if "anthropic" in providers:
        if not settings.anthropic_api_key:
            msgs.append("[FAIL] ANTHROPIC_API_KEY not set")
            ok = False
        elif not settings.anthropic_api_key.startswith("sk-ant-"):
            msgs.append("[WARN] ANTHROPIC_API_KEY does not start with 'sk-ant-' — looks malformed")
        else:
            msgs.append(f"[OK]   ANTHROPIC_API_KEY is set ({len(settings.anthropic_api_key)} chars)")

    if "openrouter" in providers:
        if not settings.openrouter_api_key:
            msgs.append("[FAIL] OPENROUTER_API_KEY not set")
            ok = False
        elif not settings.openrouter_api_key.startswith("sk-or-"):
            msgs.append("[WARN] OPENROUTER_API_KEY does not start with 'sk-or-' — looks malformed")
        else:
            msgs.append(f"[OK]   OPENROUTER_API_KEY is set ({len(settings.openrouter_api_key)} chars)")

    msgs.append(f"[INFO] judge model (fixed): {settings.llmx_judge_provider}/{settings.llmx_judge_model}")
    msgs.append(f"[INFO] default generation:  {settings.llmx_default_provider}/{settings.llmx_default_model}")

    return ok, msgs


async def call(provider_name: str, model: str, prompt: str, max_tokens: int) -> Result:
    t0 = time.perf_counter()
    try:
        provider = get_provider(provider_name)
        resp = await provider.complete(
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
        )
        return Result(
            provider=provider_name,
            model=model,
            ok=True,
            duration_s=time.perf_counter() - t0,
            text=resp.text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )
    except Exception as e:
        return Result(
            provider=provider_name,
            model=model,
            ok=False,
            duration_s=time.perf_counter() - t0,
            error=f"{type(e).__name__}: {e}",
        )


def print_result(r: Result) -> None:
    print(f"=== {r.provider} ({r.model}) ===")
    if r.ok:
        print("  status:    OK")
        print(f"  duration:  {r.duration_s:.2f}s")
        print(f"  tokens:    {r.input_tokens} in / {r.output_tokens} out")
        print(f"  response:  {r.text}")
    else:
        print("  status:    FAIL")
        print(f"  duration:  {r.duration_s:.2f}s")
        print(f"  error:     {r.error}")
    print()


async def main_async(args: argparse.Namespace) -> int:
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    for p in providers:
        if p not in ("anthropic", "openrouter"):
            print(f"Unknown provider: {p}. Allowed: anthropic, openrouter.")
            return 2

    ok, msgs = check_env(providers)
    print("=== Environment ===")
    for m in msgs:
        print(f"  {m}")
    print()

    if args.check_only:
        return 0 if ok else 2

    if not ok:
        print("Cannot --execute: required API keys are missing.")
        print("Hint: edit .env and fill in the API key(s).")
        return 2

    print(f"Prompt: {args.prompt!r}")
    print(f"NOTE: this makes {len(providers)} paid API call(s).")
    print()

    settings = get_settings()
    anthropic_model = args.anthropic_model or settings.llmx_default_model
    openrouter_model = args.openrouter_model or "deepseek/deepseek-chat"

    tasks = []
    if "anthropic" in providers:
        tasks.append(call("anthropic", anthropic_model, args.prompt, args.max_tokens))
    if "openrouter" in providers:
        tasks.append(call("openrouter", openrouter_model, args.prompt, args.max_tokens))

    results = await asyncio.gather(*tasks)

    for r in results:
        print_result(r)

    failed = [r for r in results if not r.ok]
    if failed:
        return 1

    print("=== Summary ===")
    print(f"  {len(results)} provider(s) responded.")
    print("  total tokens: " + ", ".join(f"{r.provider}={r.input_tokens + r.output_tokens}" for r in results))
    print("  durations: " + ", ".join(f"{r.provider}={r.duration_s:.2f}s" for r in results))
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Anthropic + OpenRouter LLM providers")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check-only", action="store_true", help="Only check env vars (no API calls)")
    g.add_argument("--execute", action="store_true", help="Make real API calls (costs money)")
    p.add_argument("--providers", default="anthropic,openrouter", help="Comma-separated subset")
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--anthropic-model", default=None)
    p.add_argument("--openrouter-model", default=None, help="OpenRouter model id, e.g. deepseek/deepseek-chat")
    p.add_argument("--max-tokens", type=int, default=200)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
