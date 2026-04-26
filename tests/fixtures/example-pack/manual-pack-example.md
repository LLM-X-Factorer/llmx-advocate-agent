---
schema_version: "1.0"
pack_id: "manual-2026-04-26-rag-vs-agent"
created_at: "2026-04-26T16:50:00+08:00"
created_by: "manual"

source:
  platform: "manual"
  primary_url: "https://example.com/blog/rag-is-dead"
  title: "RAG is dead, long live agents"
  author: "alice"

metrics: {}

# scout_analysis 段省略 —— 手工 pack 不强制提供
# 这种情况下，advocate Phase 2.5 从 RawMaterial 起步，没有种子判断可推翻
---

# RAG is dead, long live agents

## 来源元信息

- **来源**：博客文章（手工整理）
- **整理日期**：2026-04-26
- **目的**：测试 advocate-agent Phase 1 在「无 scout_analysis」情况下能正常工作

## 原文正文

> 这里放完整的原文 markdown 化内容。本 fixture 仅用于 schema 校验，
> 不要求是真实的可发布素材。

随着 agent 能力的演进，越来越多人开始质疑 RAG 是否还有存在的必要。
本文从工程实践角度论证：RAG 没有死，但它的角色发生了变化——
从"主角"变成了"agent 的一个工具"。

## 评论区精华

### @user1
RAG 的问题是召回质量不可控，agent 至少能在多次尝试后纠错。

### @user2
评论 1 说反了。Agent 的问题是耗 token、耗时间——RAG 一次到位的成本优势依然成立。

## 相关讨论

- 无（手工 pack 通常不附跨平台讨论）
