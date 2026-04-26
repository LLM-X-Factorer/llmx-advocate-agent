# P2.5 — Core Judgment Extraction

> Source: chinese-content-workflow SKILL.md §Phase 2.5 + dbs-deconstruct (Wittgenstein/Austrian).
> Hard rule: this phase MUST produce a one-sentence judgment that passes 4 QA gates (§5.1).
> Failing here doesn't get retried with a "better prompt" — the engine retries with a
> different angle (fallback to P1.5).

## Inputs
- Source pack body: {{ source_pack.body_markdown }}
- Source pack scout_analysis (may be null): {{ source_pack.scout_analysis }}
- Chosen angle: {{ angle }}
- Layer profile (tier, scores): {{ layer_profile }}

## judgment_seed handling (CRITICAL)

If `source_pack.scout_analysis.judgment_seed` is provided, treat it as a **starting point**, not a finished verdict.

You have two valid outputs:

1. **Keep the seed** — fill `seed_judgment=<the seed>`, `overrode_seed=False`.
   Still surface your own reasoning to validate it; if you can't independently arrive at the seed, you don't actually understand it — go to option 2.

2. **Override the seed** — your independent analysis lands on a different judgment.
   Fill `seed_judgment=<the seed>`, `overrode_seed=True`, `override_reason=<why your judgment is more accurate>`.

If `judgment_seed` is null (manual pack / scout had nothing), fill `seed_judgment=None`, `overrode_seed=False`.

**Either way, the 4 P2.5 QA gates run on the final `full_sentence`** (§5.1) — the seed gets no immunity.

## Output schema (JSON)
```json
{
  "surface": "...",
  "transition": "但其实 / 真正原因是 / 背后是 / 本质上",
  "deeper_essence": "...",
  "full_sentence": "...",
  "seed_judgment": "<seed if any, else null>",
  "overrode_seed": false,
  "override_reason": null
}
```

## Extraction techniques (use one or combine)

1. **"所以呢" 链** — keep asking "so what?" until you reach a structural insight.
2. **"和 X 有什么不同" 对比** — what changes structurally compared to prior art?
3. **"如果我是决策者" 视角** — what would a decision-maker care about that the article skipped?

## Wittgenstein/Austrian sanity checks (from dbs-deconstruct)
- 伪概念检测：去掉关键词，用大白话还能说清吗？
- Question vs Problem：是有标准答案的事，还是需要实践的事？
- 主观价值论：判断是否预设了"客观价值"？
- 价格信号：判断能否被市场行为验证？

## Forbidden outputs
- 复述原文（违反 P2.5_uniqueness）
- 必须看原文才能理解（违反 P2.5_independent_value）
- > 50 字（违反 P2.5_brevity）
- 包含来源背书短语（违反 P2.5_anti_relay）

## Final check before returning
Read your full_sentence aloud. If it takes longer than 15 seconds at 3.2 chars/sec, shorten.
