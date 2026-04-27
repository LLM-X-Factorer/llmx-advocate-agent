# Output Archive Schema

> 这份文件是 `llmx-advocate-agent`（生产者）和 `llmx-advocate-outputs`（消费者，结构化归档仓）之间的接口契约。
> 两个项目仓库各保留一份完全相同的副本，schema 改动必须双仓同步。
> 与 `docs/source-pack-schema.md` 形成对称：scout → packs → advocate → outputs。

## 设计原则

1. **git-native**：每个 task 一个目录，git diff 友好，文件级回滚可行
2. **自包含**：所有归档目录里的文件都不依赖外部资源，包括 source pack 的内联拷贝
3. **失败也归档**：失败任务进 `failures/` 子树，保留信号但不污染主目录
4. **写者去重**：advocate 内 `core/export.py:persist_to_disk` 是单一写入入口；CLI 通过 API 间接走同一路径
5. **失败优于撒谎**：能拿到就完整拿到；P4/P6 缺失就字段缺失，不脑补

## 目录结构

```
llmx-advocate-outputs/
├── README.md                    # 仓库说明，由 scripts/output-repo-readme-template.md 生成
├── 2026-04-27/                  # task.created_at 当地日期
│   ├── 01KQ6PXR.../             # task.id（ULID）
│   │   ├── task.json            # 元数据（必有）
│   │   ├── summary.md           # 人读摘要（必有）
│   │   ├── video.json           # P4 完整 Video JSON（如 P4 通过）
│   │   ├── publishing.json      # P6 标题/简介/置顶（如 P6 通过）
│   │   └── source-pack.md       # 内联的 source pack 原文（如 task 提交时给了 pack_content）
│   └── 01KQ7HM.../
│       └── ...
├── 2026-04-28/
│   └── ...
└── failures/                    # 状态为 FAILED 的任务进这里
    └── 2026-04-27/
        └── 01KQ6PSQ.../
            ├── task.json
            ├── error.md         # 失败原因 + 最后一次 PhaseRun 的 QA gates / traceback
            └── source-pack.md   # 仍写一份 pack 拷贝便于复盘
```

**关键约束**：
- 主目录（success）和 `failures/` 互斥——同一个 task.id 只出现一次
- 文件写入是原子的（write to `.tmp`, rename）——git push cron 永远看不到半成品

## task.json schema

### COMPLETED 任务

```json
{
  "task_id": "01KQ6PXR...",
  "title": "DeepSeek-v4 推理范式拆解",
  "status": "completed",
  "source_pack_id": "hn-2026-04-27-43891234",
  "tier": "留存",
  "judgment": "表面看是X，实则是Y。",
  "theme": "稀疏模型的红利在内存墙上被讨价还价",
  "llm_provider": "openrouter",
  "llm_model": "deepseek/deepseek-chat",
  "created_at": "2026-04-27T10:00:00+00:00"
}
```

### FAILED 任务

```json
{
  "task_id": "01KQ6PSQ...",
  "title": "...",
  "status": "failed",
  "source_pack_id": "manual-test-001",
  "failed_phase": "P2.5",
  "failed_attempts": 5,
  "llm_provider": "openrouter",
  "llm_model": "deepseek/deepseek-chat",
  "created_at": "2026-04-27T05:32:00+00:00"
}
```

字段说明：
- `task_id` / `title` / `created_at`：与 advocate 数据库一致
- `source_pack_id`：从 P1 输出的 `SourcePack.pack_id` 抽取；这是**消费者去重的 key**——`scripts/cron-consume-packs.sh` 跑前会扫所有 `task.json` 集出已处理的 pack_id 集合，跳过重复
- `judgment`：P2.5 的 `full_sentence`（如 P2.5 通过）
- `theme`：P2.6 的 `theme`（如 P2.6 通过）
- `tier`：P2 的 `tier`（如 P2 通过）
- `failed_phase` / `failed_attempts`：仅 FAILED；指出哪个 phase 触发任务终止

## summary.md（仅 COMPLETED）

人读的精简摘要，给非工程师看：

```markdown
# DeepSeek-v4 推理范式拆解

- task_id: `01KQ6PXR...`
- status: completed
- tier: 留存
- source_pack_id: `hn-2026-04-27-43891234`
- model: `openrouter/deepseek/deepseek-chat`

## Theme
稀疏模型的红利在内存墙上被讨价还价

## Core Judgment
表面看是2-bit量化让MoE模型跑上消费级硬件，实则暴露稀疏模型的红利正被内存墙和路由开销吞噬。

## Title Options
1. **[T-3]** 2-bit量化MoE：稀疏模型红利与内存墙的拉锯
   - tier=留存 决策者口味，落判断的对立面
2. **[T-7]** MoE 跑上消费级硬件，但红利正在被吞噬
   - 悬念前置 + 反差
3. **[T-2]** 稀疏模型的 2-bit 临界点，赢家是路由专家

## Description
🎯 看点 1：...
📊 看点 2：...
💡 看点 3：...

## Pinned Comment
\`\`\`
🎬 章节时间戳：
00:00 量化认知的颠覆
02:18 选择性量化策略
\`\`\`
```

## error.md（仅 FAILED）

复盘用，含失败 phase 的 QA gates 和 traceback：

```markdown
# Failure: <task title>

- task_id: `01KQ6PSQ...`
- failed_phase: `P2.5`
- failed_attempts: 5
- source_pack_id: `manual-test-001`
- model: `openrouter/deepseek/deepseek-chat`

## QA Gates (last attempt)
- ✅ `P2.5_uniqueness` — 判断 X 在原文中未直接表述
- ❌ `P2.5_anti_relay_judge` — judgment relies on source backing

## Error
\`\`\`
QA gates failed: P2.5_anti_relay_judge
\`\`\`

## Traceback
\`\`\`
(only present for ERROR-status PhaseRuns; absent for QA_FAILED_TERMINAL)
\`\`\`
```

## video.json / publishing.json

这两个文件是 P4 / P6 phase 的**完整、未修改**输出，直接对应 `docs/source-skill/extracted/chinese-content-workflow/resources/VIDEO_JSON_REFERENCE.md` 的 schema。下游（视频自动渲染系统）直接消费 video.json，无需再处理。

## source-pack.md

如果创建 task 时给了 `pack_content`（API 通常如此），这里写一份原始 pack 内容的拷贝。如果给的是 `pack_path`（本地路径），则跳过——避免悬挂引用。

**为什么要内联**：scout 仓后续可能 rebase / GC 旧文件，输出仓必须自包含才能在事后还原"这个判断是基于哪段原文做出的"。

## 兼容性策略

- 加新可选字段 → 不破坏；下游应忽略未知字段
- 删除/重命名字段 → 破坏性，需双仓同步 PR
- `task.json` 顶层字段顺序无强制
- 文件名不允许含空格 / 中文（task.id 是 ULID 已保证）

## 写入语义

- 写入由 `core/export.py:persist_to_disk` 触发，仅在 task 进入 terminal status (COMPLETED / FAILED) 时
- 同一个 task.id 写入是**幂等的**——重跑（人工 `task qa` 重跑 QA 之后状态不变）会原地覆盖；这跟 git diff 友好
- PAUSED_FOR_HUMAN 状态**不写**——这不是终态
- 失败但 `qa_failed_terminal` → fallback 链没耗尽时**不写**——只有真正进入 FAILED 才写

## 不在归档里的东西

- 完整的 PhaseRun 历史（所有 attempt + retry + qa_result）：保留在 advocate DB，归档只保留成品
- LLM 调用的 token 使用 / 成本：同上
- 中间 phase 输出（P1/P1.5/P2/P3/P5）：归档只关心 P2/P2.5/P2.6/P4/P6（消费者关心的）

需要查这些信息时去 advocate Web UI（V0.2）或 CLI `task show`。
