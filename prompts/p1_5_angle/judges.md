# P1.5 Judge prompts

Used by core/qa for `P1.5_not_product_announcement`. Returns binary JSON
{"passed": bool, "rationale": str}.

## P1.5_not_product_announcement

```
Topic angle being judged:
- core_tension: {{ angle.core_tension }}
- your_position: {{ angle.your_position }}
- why_readers_care: {{ angle.why_readers_care }}

Question: is this angle just a product launch / news announcement frame,
i.e. "X released Y, here's what it does"?

- product announcement frame → passed=false
- there's a genuine debate, contradiction, counterintuitive claim,
  or analytic stance → passed=true

Return JSON: {"passed": bool, "rationale": "..."}
```
