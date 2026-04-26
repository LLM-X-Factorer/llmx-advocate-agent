# P2.5 Judge Prompts

Used by core/qa/judges.py for P2.5_uniqueness / P2.5_independent_value / P2.5_anti_relay /
P2.5_cognition_gap. Always returns binary JSON {"passed": bool, "rationale": str}.

## P2.5_uniqueness

```
判断："{{ judgment.full_sentence }}"
原文核心摘要："{{ raw_material_summary }}"

问题：原文是否已经直接表述了这个判断（哪怕用不同词句）？
- 如果是，passed=false（这是复述，不是判断）
- 如果不是（这是从原文中推出的解读 / 角度 / 洞察），passed=true

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P2.5_independent_value

```
仅看这句话："{{ judgment.full_sentence }}"

不参考任何上下文。这句话本身是否表达了一个有价值的观点？
- 必须能让一个不知情的读者从中获得信息或视角
- 不能是"需要看原文才能理解"的指代

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P2.5_anti_relay

```
判断："{{ judgment.full_sentence }}"

如果在判断前面加上"今天聊一个 HN 热榜的文章"或"最近 XX 很火，我来解读"——
这是否让判断显得多余（说明判断本身已经有价值）？
还是说判断需要这个来源背书才有吸引力？

- 多余 → passed=true（判断本身够强）
- 不多余 → passed=false（判断需要靠来源借力，太弱）

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P2.5_cognition_gap

```
话题："{{ topic }}"
你的判断："{{ judgment.full_sentence }}"
同行解读样本（最多 3 段）："{{ peer_takes }}"

你的判断 vs 同行解读，认知落差是否明显？
- 同行只看到表面，你看到结构 → passed=true
- 和同行差不多 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```
