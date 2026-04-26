# P1.5 — Topic Angle Discovery

> Source: chinese-content-workflow SKILL.md §Phase 1.5.
> Goal: turn a source pack into a *chosen angle* — not just a summary, but the
> specific entry point for an analytical video.

## Inputs

- Source pack title: {{ source_pack.source.title }}
- Source platform: {{ source_pack.source.platform }}
- Pack body (truncated):
{{ body_excerpt }}

{% if source_pack.scout_analysis %}
- Scout analysis:
  - matched_keywords: {{ source_pack.scout_analysis.matched_keywords }}
  - controversy_signals: {{ source_pack.scout_analysis.controversy_signals }}
  - judgment_seed (gift, not command): {{ source_pack.scout_analysis.judgment_seed or "—" }}
{% endif %}

## What you're looking for

The difference between a viral piece and a forgettable one is the **angle**, not the content.
Find one of these signals in the pack:

| Signal | Why it works |
|--------|-------------|
| Controversy | Triggers debate; readers come to defend / attack |
| Counterintuitive data | Challenges assumed beliefs |
| Underdog / constraint story | Emotional narrative |
| Practical contradiction (high benchmark, poor real-world) | Relatable frustration |
| Expert disagreement | Shows the question is non-trivial |

Avoid the boring default: "product launch announcement" / chronological "what happened".

## Output schema (JSON, strict)

```json
{
  "hook_source": "where you found the angle (HN comment, scout controversy_signal, body paragraph quote, etc.)",
  "core_tension": "the debate/question you're addressing",
  "your_position": "what unique perspective you'll bring (one sentence)",
  "why_readers_care": "connection to the reader's interests/concerns"
}
```

Output ONLY the JSON object. No markdown fences, no commentary.

## Constraints

- Reuse `scout_analysis.controversy_signals` and `judgment_seed` if relevant; you can override.
- The angle must be specific enough that someone reading just `your_position` sees a real claim.
- "讨论很热烈" / "值得关注" are non-claims. Reject them as candidate positions.
