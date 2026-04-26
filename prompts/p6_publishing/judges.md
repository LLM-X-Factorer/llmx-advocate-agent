# P6 Judge Prompts

## P6_title_reflects_judgment

```
P2.5 核心判断: "{{ judgment_full }}"

候选标题列表:
{{ titles_block }}

判断这些标题**整体上**是否体现了核心判断的张力：
- 至少 2/3 标题指向判断的核心矛盾 / 反差 / 洞察 → passed=true
- 标题只是"X 的解读"、"Y 是什么"这种主题陈述，未触及判断 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P6_title_matches_tier

```
内容层级 tier: "{{ tier }}"
候选标题:
{{ titles_block }}

判断标题风格是否匹配 tier：
- 引流：震撼数字 / 反常识 / 中国视角 / 热点判断 — 钩子强、门槛低
- 留存：身份认同 / 决策框架 / 案例复盘 / 本质洞察 — 体现观点
- 转化：痛点场景 / 能力缺口 / 完整版引导 — 暗示付费内容

匹配 → passed=true；明显跑偏到另一层 → passed=false。

返回 JSON: {"passed": bool, "rationale": "..."}
```
