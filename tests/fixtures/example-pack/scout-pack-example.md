---
schema_version: "1.0"
pack_id: "hn-2026-04-26-43891234"
created_at: "2026-04-26T10:30:00+08:00"
created_by: "llmx-scout-agent@0.1.0"

source:
  platform: "hacker_news"
  primary_url: "https://news.ycombinator.com/item?id=43891234"
  original_url: "https://example.com/blog/rag-is-dead"
  title: "RAG is dead, long live agents"
  author: "alice"
  published_at: "2026-04-25T14:00:00Z"

metrics:
  hn_score: 423
  hn_comments: 187

scout_analysis:
  matched_keywords: ["RAG", "agent", "retrieval"]
  llm_score: 8.5
  llm_reasoning: "评论区围绕『RAG 是否被 agent 取代』有明确分裂，HN 用户和 Reddit r/LocalLLaMA 出现观点对立，符合 controversy 信号。"
  judgment_seed: "表面是 RAG 被 agent 取代，实则是检索范式从『一次性召回』转向『迭代式探索』"
  suggested_layer: "留存"
  controversy_signals:
    - type: "expert_disagreement"
      evidence: "Andrej K. 与 Jerry Liu 在 X 上观点对立"
    - type: "counterintuitive_data"
      evidence: "MTEB benchmark 高分模型在生产环境召回率反而下降"
---

# RAG is dead, long live agents

## 来源元信息

- **平台**：Hacker News（[HN-43891234](https://news.ycombinator.com/item?id=43891234)）
- **原文**：[example.com/blog/rag-is-dead](https://example.com/blog/rag-is-dead)
- **作者**：alice · 2026-04-25
- **热度**：423 分 / 187 评论

## 原文正文

[完整 markdown 化后的原文]

## 评论区精华（Top 5 by score）

### @user1（234 分）
RAG 的问题是召回质量不可控...

### @user2（189 分）
评论 1 说反了...

## 相关讨论

- [r/LocalLLaMA 讨论帖](https://example.reddit.com/...) — 多数人支持 hybrid 方案
- [Twitter thread by @karpathy](https://example.x.com/...) — 提出"agent loops 才是新 RAG"的观点
