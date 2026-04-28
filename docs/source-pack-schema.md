# Source Pack Schema

> 这份文件是 `llmx-scout-agent`（生产者）和 `llmx-advocate-agent`（消费者）之间的接口契约。
> 两个项目仓库各保留一份完全相同的副本。任何变更必须走双向 PR 同步。

## 设计原则

1. **人类可读可写**：Markdown + YAML frontmatter，git diff 友好，必要时手工编辑可行
2. **LLM 处理友好**：结构清晰、字段语义明确，下游 LLM 不需要复杂解析
3. **自包含**：消费方不应需要回到原始 URL 重新抓取
4. **可演进**：`schema_version` 字段支持平滑升级
5. **失败优于撒谎**：能拿到就完整拿到，拿不到就显式 `null`，禁止脑补

## 文件存储约定

- **路径**：`output/packs/YYYY-MM-DD/<slug>.md`
- **命名**：日期 + 短 slug（如 `rag-vs-agent-debate.md`），slug 由标题截断+连字符化
- **编码**：UTF-8，LF 行尾
- **大小**：单文件建议 < 200KB；超长原文做摘要 + 关键章节保留，整文存到同目录的 `<slug>.fulltext.md`

## 完整 Schema（v1.0）

```markdown
---
schema_version: "1.0"
pack_id: "hn-2026-04-26-43891234"        # 全局唯一 ID
created_at: "2026-04-26T10:30:00+08:00"  # ISO 8601 带时区
created_by: "llmx-scout-agent@0.1.0"     # 工具名@版本，手工产出用 "manual"

source:
  platform: "hacker_news"                # 见下方枚举
  primary_url: "https://news.ycombinator.com/item?id=43891234"  # 讨论入口
  original_url: "https://example.com/blog/rag-is-dead"          # 真正的内容源（可与 primary 相同）
  title: "RAG is dead, long live agents"
  author: "alice"                        # 作者署名，未知填 null
  published_at: "2026-04-25T14:00:00Z"   # 原文发布时间，未知填 null
  language: "en"                         # ISO 639-1

metrics:                                 # 各平台按需填写，未采集到的填 null
  hn_score: 423
  hn_comments: 187
  github_stars: null
  github_stars_today: null
  reddit_upvotes: null
  reddit_comments: null
  x_likes: null
  x_reposts: null

scout_analysis:                          # scout 的预判，下游可参考也可推翻
  matched_keywords: ["RAG", "agent", "retrieval"]
  llm_score: 8.5                         # 0-10
  llm_reasoning: "评论区围绕『RAG 是否被 agent 取代』有明确分裂..."
  judgment_seed: "表面是 RAG 被 agent 取代，实则是检索范式从『一次性召回』转向『迭代式探索』"
  suggested_layer: "留存层"               # 引流层 | 留存层 | 转化层 | unsure
  controversy_signals:                   # 对应 SKILL.md Phase 1.5 的高互动信号
    - type: "expert_disagreement"        # 见下方枚举
      evidence: "Andrej K. 与 Jerry Liu 在 X 上观点对立"
      url: "https://x.com/karpathy/status/..."  # 可选
  notes: null                            # scout 的额外备注，可选

harvest:                                 # 抓取过程的元数据
  harvested_at: "2026-04-26T10:25:00+08:00"
  fulltext_extracted: true               # 原文是否成功 markdown 化
  fulltext_method: "trafilatura"         # trafilatura | readability | playwright | manual
  fulltext_external_file: null           # 若过长另存，填相对路径如 "rag-vs-agent-debate.fulltext.md"
  comments_count_fetched: 5              # 实际抓取的评论数
  warnings: []                           # 抓取过程中的告警，如 "paywall detected"
---

# RAG is dead, long live agents

## 来源元信息

- **平台**：Hacker News（[HN-43891234](https://news.ycombinator.com/item?id=43891234)）
- **原文**：[example.com/blog/rag-is-dead](https://example.com/blog/rag-is-dead)
- **作者**：alice · 2026-04-25
- **热度**：423 分 / 187 评论

## Scout 的预判

> ⚠️ 以下为 scout 阶段的初步判断，下游 advocate-agent 应当校验、深化或推翻，不可直接采用。

**判断种子**：表面是 RAG 被 agent 取代，实则是检索范式从「一次性召回」转向「迭代式探索」

**建议层级**：留存层

**争议信号**：
- 专家分歧：Andrej K. 与 Jerry Liu 在 X 上观点对立

## 原文正文

[完整 markdown 化后的原文。如过长，此处放摘要 + 关键章节，完整版见 fulltext_external_file]

## 评论区精华

> Top N by score，保留作者、分数、原文 markdown

### @user1（234 分）
[评论内容]

### @user2（189 分）
[评论内容]

## 相关讨论（可选）

- [r/LocalLLaMA 讨论帖](https://...) — 一句话总结
- [Twitter thread by @karpathy](https://...) — 一句话总结
```

## Markdown body 段落约定

Body 部分有固定的小标题结构。**消费方应当区分两类段落**：

| 段落 | 性质 | 含义 |
|---|---|---|
| `## 来源元信息` | **hint** | scout 整理的元数据展示，方便人读 |
| `## Scout 的预判` | **hint** | scout 的预判，**不是事实** —— `judgment_seed` / `suggested_layer` / `controversy_signals` 在这里以可读形式重复呈现 |
| `## 原文正文` | **source** | 真实的原文内容（trafilatura 抽取或 API 拿到） |
| `## 评论区精华` | **source** | 真实的评论 |
| `## 相关讨论` | **source** | 真实的交叉链接 |

**重要约束（来自 advocate-agent 实战暴露的契约摩擦，2026-04-29）**：

> 下游若要做「LLM 输出 vs 原文」的去重 / 唯一性检查（例如 P2.5 uniqueness gate），**必须只对 source 段落比对**，不要把 hint 段落也喂给裁判。否则下游 LLM 在"采用 scout 的 judgment_seed"和"绕开和 body 里出现的 seed 重复"之间陷入死锁。

scout 把 hint 写进 body 是有意为之 —— 人读 pack 时需要直接看到 scout 在想什么。下游消费方有责任在自己机制里区分 hint vs source。

## 字段枚举

### `source.platform`
`hacker_news` | `github` | `reddit` | `x` | `product_hunt` | `zhihu` | `weibo` | `manual` | `other`

### `scout_analysis.suggested_layer`
`引流层` | `留存层` | `转化层` | `unsure`

### `scout_analysis.controversy_signals[].type`
`controversy` | `counterintuitive_data` | `underdog_story` | `practical_contradiction` | `expert_disagreement` | `other`

（对应 SKILL.md Phase 1.5 的高互动信号矩阵）

### `harvest.fulltext_method`
`trafilatura` | `readability` | `playwright` | `api`（平台 API 直接给的正文） | `manual` | `failed`

## 强制约束

- 所有时间字段必须是 ISO 8601 带时区
- `pack_id` 全局唯一，建议格式 `<platform>-<date>-<external_id>`
- `scout_analysis.llm_score` 必须在 [0, 10] 区间
- `metrics` 中至少一个字段非 null（否则 scout 没拿到任何热度信号，应该打回不打包）
- 如果 `harvest.fulltext_extracted: false`，必须在 `harvest.warnings` 里写明原因

## 校验

两个项目都应实现 schema 校验：
- scout：写文件**之前**校验，不通过不写盘
- advocate：读文件**之后**校验，不通过拒绝进入 Phase 2

推荐用 pydantic（Python）/ zod（TS）实现。schema 定义文件在两个项目里也保持同步。

## 手工产出 source pack

下游 advocate-agent 的最重要属性之一是：**没有 scout 也能跑**。手工产出 pack 的最小要求：

- `created_by: "manual"`
- `scout_analysis` 整段可以省略大部分字段，但 `judgment_seed` 强烈建议手工填一句
- `harvest.fulltext_method: "manual"`

提供 `scout pack <url>` CLI 命令辅助手工产出（自动抓取，但 scout_analysis 留空让你填）。

## 版本演进

- 破坏性变更：`schema_version` 主版本号 +1（`1.0` → `2.0`），advocate 必须显式声明支持哪些主版本
- 兼容性变更（加新可选字段）：次版本号 +1（`1.0` → `1.1`），双方继续工作
- 任何变更都走 PR + 双仓库同步 commit
