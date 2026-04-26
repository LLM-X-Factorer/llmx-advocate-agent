# P2.6 — Cognitive Deepening (Information → Thinking → Insight)

> Source: chinese-content-workflow SKILL.md §Phase 2.6.
> 目标：把 P2.5 提取的判断从 "信息层 / 思考层 / 洞察层" 三层验证，并产出能落地的 theme。

## ⚠️ OUTPUT LANGUAGE: 中文

所有字段中文输出。`theme` 必须是一句话且 ≤ 50 汉字。

## Inputs

- Source pack title: {{ source_pack.source.title }}
- Pack body excerpt:
{{ body_excerpt }}

- P2.5 judgment (the seed of this deepening pass):
  - surface: {{ judgment.surface }}
  - transition: {{ judgment.transition }}
  - deeper_essence: {{ judgment.deeper_essence }}
  - full_sentence: {{ judgment.full_sentence }}

## 三轮追问

### Round 1 — WHY（至少 2 条，最多 4 条）

针对 P2.5 判断的"深层本质"，反复问"为什么"：
- 为什么这件事会发生？
- 为什么是这个选择 / 这个数据？
- 为什么是现在，不是更早 / 更晚？
- 为什么大多数人没看到这一层？

每条 why 是一句简短中文，问出 + 简答（≤ 30 汉字）。

### Round 2 — WHAT DOES IT MEAN（至少 2 条，最多 4 条）

从单一案例**退一步**看现象：
- 这代表什么趋势 / 系统性变化？
- 对哪个群体 / 行业意味着什么？
- 挑战了哪个被普遍接受的常识？

每条 meaning 是一句中文（≤ 40 汉字）。

### Round 3 — Validation

回看 P2.5 的 `full_sentence`：
- 三轮追问之后，这个判断是否仍然成立？
- 如果需要修正，新 theme 是什么？
- 修正后是否更接近"洞察层"（不只是"思考层"）？

`validation_notes` 写一段中文 ≤ 100 汉字，说明判断站住或修正的理由。

## Theme（最终落地）

`theme` 是 P2.6 给后续 phase 的**唯一交付**——一句中文，≤ 50 汉字。
它要么 **沿用** P2.5 的 `full_sentence`（如果三轮验证后仍然站得住），
要么 **微调** 让判断更接近洞察层。

## 输出格式（严格 JSON）

```json
{
  "why_round": ["为什么1：……", "为什么2：……"],
  "meaning_round": ["意味着1：……", "意味着2：……"],
  "validation_notes": "<判断站住 or 修正的理由，中文 ≤100字>",
  "theme": "<最终一句话主题，中文 ≤50字>"
}
```

仅返回 JSON 对象本身，无 markdown 围栏，无解释。

## 4 项 Depth Test 自检（生成前默念）

返回前用这 4 道题自检 `theme`：

1. **超越表面**：theme 是否避免了 "X 很厉害 / 有问题 / 重要 / 强大" 这种形容词式判断？
2. **挑战默认**：theme 是否能让读者重新思考一个被默认接受的事？
3. **可迁移**：这个洞察能否套到至少 2 个其他类似案例？
4. **去钩子独立**：把热点 / 争议 / 数字钩子拿掉，theme 是否仍然成立？

任何一项不过 → 重写 theme。

## 反面示例（不合格的 theme）

| theme | 为什么不合格 |
|---|---|
| "RAG 真的很重要" | 形容词式判断，违反 1 |
| "这个新模型太强了" | 形容词 + 钩子依赖，违反 1+4 |
| "Agent 是未来" | 抽象口号，违反 2+3（无法挑战默认，也不可迁移到具体案例）|
