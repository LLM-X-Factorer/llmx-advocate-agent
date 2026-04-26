# Source Pack Schema v1.0

> **本文档是 `llmx-scout-agent` ⟷ `llmx-advocate-agent` 之间的接口契约**。
>
> 任何 schema 变更必须**同步两边**：在两个 repo 里 commit 完全一致的副本，CI 跑 hash 比对（见 §6）。
> 当前只有 advocate-agent 项目存在；scout-agent 启动时，把本文件 cp 过去作为对方的契约副本。

## 1. 设计哲学

- **文件即契约**：上游产物是一个完整、自洽的 markdown 文件；下游不再做网络抓取。
- **人类可手写**：scout 缺位时，LE PPW 可以手工写一个符合 schema 的 pack 直接喂下游。
- **schema 演进可见**：所有变更走 PR + 双向同步，禁止隐式漂移。

## 2. 文件格式

**Markdown + YAML frontmatter**。文件扩展名 `.md`。

```
---
{ YAML frontmatter (machine-readable metadata) }
---

# {pack title}

{ markdown body — 来源元信息、原文正文、评论精华、相关讨论 }
```

frontmatter 是机器读的（schema 校验在此），body 是人 + LLM 都读的。

## 3. Frontmatter 字段

### 3.1 顶层

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `schema_version` | ✅ | string | 当前为 `"1.0"`。下游会校验版本兼容 |
| `pack_id` | ✅ | string | 唯一 ID，建议格式 `<source>-<date>-<external_id>` |
| `created_at` | ✅ | ISO 8601 | 含时区 |
| `created_by` | ✅ | string | `llmx-scout-agent@<version>` 或 `manual` |
| `source` | ✅ | object | 见 §3.2 |
| `metrics` | 可选 | object | 见 §3.3，按平台填写已有指标 |
| `scout_analysis` | 可选 | object | 见 §3.4。**手工 pack 可省略整段**；scout 产出必含 |

### 3.2 `source`

| 字段 | 必需 | 说明 |
|------|------|------|
| `platform` | ✅ | 枚举：`hacker_news` / `github` / `reddit` / `x` / `producthunt` / `manual` / `other` |
| `primary_url` | ✅ | scout 抓取的入口 URL（HN 帖子 URL / GitHub trending 页 / 自己的笔记链接等） |
| `original_url` | 可选 | 原文 URL（如果 primary_url 是讨论站点） |
| `title` | ✅ | 原文标题 |
| `author` | 可选 | 作者名 |
| `published_at` | 可选 | ISO 8601 |

### 3.3 `metrics`（按平台按需填写）

```yaml
metrics:
  hn_score: 423
  hn_comments: 187
  github_stars: null
  github_stars_today: null
  reddit_upvotes: null
  reddit_comments: null
  x_likes: null
  x_replies: null
```

### 3.4 `scout_analysis`（scout 产出 / 手工可省）

| 字段 | 必需（如果整段存在） | 说明 |
|------|------|------|
| `matched_keywords` | 可选 | 关键词初筛命中的词列表 |
| `llm_score` | 可选 | scout LLM 评分 0-10 |
| `llm_reasoning` | 可选 | 评分理由 |
| `judgment_seed` | 可选 | ⭐ 一句话种子判断（"表面 X，但其实 Y"格式）。**advocate Phase 2.5 可推翻** |
| `suggested_layer` | 可选 | `引流` / `留存` / `转化`（与 advocate 内部 Tier 枚举对齐，**不带"层"字**） |
| `controversy_signals` | 可选 | list of {type, evidence}，对应 chinese-workflow Phase 1.5 高互动信号 |

### 3.5 完整 frontmatter 示例

```yaml
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
  llm_reasoning: "评论区围绕『RAG 是否被 agent 取代』有明确分裂..."
  judgment_seed: "表面是 RAG 被 agent 取代，实则是检索范式从『一次性召回』转向『迭代式探索』"
  suggested_layer: "留存"
  controversy_signals:
    - type: "expert_disagreement"
      evidence: "Andrej K. 与 Jerry Liu 在 X 上观点对立"
---
```

## 4. Body 结构（推荐章节）

body 是 markdown 自由文本，但下游 advocate-agent 期望以下章节存在（章节标题用 `## ` 二级标题）：

- `## 来源元信息` — 来源、热度、作者等的人话总结
- `## 原文正文` — 完整 markdown 化的原文
- `## 评论区精华` — Top 5 高分评论
- `## 相关讨论` — 跨平台交叉引用（可选）

**advocate-agent 不强制要求章节标题完全一致**——只要 body 包含可识别的"原文正文"段落即可。但 scout-agent 应严格按照上述章节产出。

## 5. judgment_seed 的语义边界（CRITICAL）

> **种子是礼物，不是命令。**

- scout 产出 `judgment_seed` 是给 advocate Phase 2.5 一个**起点**，不是终点
- advocate Phase 2.5 必须能**推翻**种子（在 `Judgment` 输出中通过 `overrode_seed=true` + `override_reason` 显式记录）
- 推翻后仍然必须通过 P2.5 的 4 项强制 QA（独特性 / 独立价值 / 简洁性 / 反搬运）
- 即便 P2.5 沿用了种子（未推翻），4 项 QA 也照跑——避免 scout 出错时种子污染下游

## 6. 双向同步纪律

两个 repo 里各放一份**完全一致**的本文件。变更流程：

1. 在任一 repo 提 PR 改 schema
2. PR 检查脚本（CI）会跑：
   ```bash
   curl -fsSL https://raw.githubusercontent.com/LLM-X-Factorer/llmx-<other>-agent/main/docs/source-pack-schema.md \
     | sha256sum
   sha256sum docs/source-pack-schema.md
   ```
   两个 hash 不一致 → CI 失败
3. 同步 PR 合到另一边（hash 重新一致）后，本 PR 才能 merge
4. 任何 schema_version 升级（次版本号或主版本号），同时改 schema_version 字段值

> ⚠️ V0.1 仅有一个 repo，hash 比对脚本暂不启用；scout-agent 立项当天必须实施。

## 7. Pydantic 数据模型映射（advocate 侧）

实现在 `src/llmx_advocate/core/models.py` 的 `SourcePack` 类。校验在 P1 phase 入口完成，不通过 → 任务直接 fail（不重试，因为是输入数据错）。

## 8. Schema 演进规则

- 字段**只增不减**：旧字段标记 deprecated 至少保留 1 个 minor 版本
- 任何字段必需性（required → optional 或反之）变更视为 **major** 版本
- 增字段视为 **minor** 版本
- pack 文件首行 `schema_version: "X.Y"`，下游按此选择校验 schema
