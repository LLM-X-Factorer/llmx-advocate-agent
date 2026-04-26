# P3 — Core Information Extraction

> Source: chinese-content-workflow SKILL.md §Phase 3 + dbs-hook 5-dim material checklist.
> 目标：从 source pack 提取够支撑 P4 视频生成的素材；按 5 个维度分类，至少 3 维非空。

## ⚠️ OUTPUT LANGUAGE: 中文

所有输出字段中文。空字段返回空数组 `[]`，不要省略键。

## Inputs

- Source pack title: {{ source_pack.source.title }}
- Pack body excerpt:
{{ body_excerpt }}

- Theme (from P2.6) — 整个视频的核心主题，所有 finding 都应该围绕它：
  "{{ theme }}"

- Judgment (from P2.5) — 一句话核心判断：
  "{{ judgment.full_sentence }}"

## 5 维素材分类（dbs-hook 补强）

P3 强制门：以下 5 维**至少 3 维非空**。空着的维度返回 `[]`。
不要硬凑，没有就空——但凑不齐 3 维，pack 本身可能不适合做。

### 维度 1：冲击数据（key_data_points）

具体数字 + 含义。例：`"460 万美元 — AI 在模拟环境中成功'盗取'的金额"`

格式：`"<数据>: <含义>"` 或 `"<数据> — <含义>"`，每条一句中文。

### 维度 2：转变 / 反差故事（stories）

之前 vs 之后 / 谁本来 vs 后来。结构性故事，不是闲谈。

每条：
```json
{ "title": "<10字内标题>", "summary": "<≤80字总结>" }
```

### 维度 3：可独立成立的金句（quotable_lines）

能脱离上下文独立成立的观点 / 反常识表述。原文金句优先；也可以是你提炼的。

每条一句中文，≤ 30 字。

### 维度 4：权威背书（authority_anchors）

人物 / 机构 / 报告 / 排名。例：`"Anthropic 官方报告"`、`"Andrej Karpathy 评论"`、`"MTEB benchmark 数据"`。

每条一行字符串。

### 维度 5：痛点共鸣（pain_points）

目标受众的具体焦虑 / 错误做法。例：`"工程师以为提高 chunk size 就能改善 RAG"`、`"决策者不知道何时该上 agent"`。

每条 ≤ 50 字中文。

## Findings（核心发现 3-5 条 — 必填）

围绕 theme 的核心论点，每条 1 个论点 + 数据 / 出处。最少 3 条，最多 5 条。

```json
{
  "description": "<论点本身，一句中文 ≤ 60 字>",
  "key_data": "<支撑数据 / null>",
  "source": "<原文出处提示 / null>"
}
```

## Advocate Interpretation（必填）

布道者视角的解读：对学习者 / 实践者 / 决策者意味着什么？≤ 200 字中文段落。

## 输出格式（严格 JSON）

```json
{
  "findings": [
    { "description": "...", "key_data": "...", "source": "..." }
  ],
  "key_data_points": ["...", "..."],
  "stories": [{ "title": "...", "summary": "..." }],
  "quotable_lines": ["...", "..."],
  "authority_anchors": ["...", "..."],
  "pain_points": ["..."],
  "advocate_interpretation": "..."
}
```

仅返回 JSON 对象，无 markdown 围栏，无解释。
