# llmx-scout-agent — Project Bootstrap Prompt

> 这是 LE PPW 在 2026-04-26 的 advocate-agent 评审中给出的 scout 项目启动 prompt。
> **当前 scout-agent 项目尚未启动**——按"先建下游再建上游"原则，advocate V0.1 跑通后再立项。
> 立项当天直接把这份内容作为新 repo 的 CLAUDE.md / 启动 prompt 使用。

---

## Project: llmx-scout-agent

### 项目定位

每天主动出击，从海外 AI 圈高质量信息源寻找有「分析师切入空间」的选题，把原文 + 讨论 + 角度种子扒下来整理好，输出**标准化源文件**给下游 agent 消费。

**核心价值**：替代「我每天刷 HN/GitHub/Reddit + 手工复制原文 + 手工读评论区」这套耗时巨大的人工流程。

**不替代的**：核心判断的最终确定、内容生产、发布。这些是下游 `llmx-advocate-agent` 的事。

### 关于使用者

LE PPW，AI 工程布道者，运营 B 站频道 LLM-X-Factors。
公司 tenisinfinite（香港）。已有下游内容生产 agent（`llmx-advocate-agent`），需要稳定供应高质量、整理好的选题源文件。

### 必读资源

- `docs/source-pack-schema.md` — 源文件 Schema 规范（接口契约，从 advocate-agent 项目的同名文件 cp 过来，必须保持一致）
- `docs/upstream-context.md` — 下游 advocate-agent 的工作流摘要（说明 scout 的输出会被怎么使用）
- `docs/inspiration/TrendRadar-notes.md` — 参考但不复刻 TrendRadar 的笔记

**读完这三份再设计。**

### 系统架构

#### 三阶段流水线

```
[ Discover ] → [ Filter & Score ] → [ Harvest & Pack ] → [ Notify ]
```

**1. Discover · 数据源采集**

V0.1 仅支持三个高 ROI 源（够用就好）：
- Hacker News：官方 Firebase API（免费、无限制、稳定）
- GitHub Trending：RSS 或第三方 API
- Reddit：r/LocalLLaMA、r/MachineLearning、r/singularity 的 JSON 端点（必须带 User-Agent）

预留扩展点：未来加 Product Hunt、X 关注列表、知乎热榜。

**2. Filter & Score · 两阶段筛选**

- **关键词初筛**（参考 TrendRadar 的 `frequency_words.txt` 语法：基础词、必须词 `+`、过滤词 `!`、正则 `/pattern/`、显示名 `=>`）
- **LLM 二次评分**：对初筛通过的候选用 Claude 打分（0-10），关键提问：
  > 「这条信息有没有『表面 X，但其实 Y』的判断空间？如果有，给出一句话的 judgment_seed。如果没有，0 分。」

  这条提示词是 scout 的灵魂，必须单独打磨、版本化管理（`prompts/scoring.md`）。

**3. Harvest & Pack · 完整抓取并打包**

> 这是 scout 的核心价值环节，不是把 URL 推给我就完事。

对评分 ≥ 阈值的候选：
- 抓取原文 → markdown 化（推荐用 trafilatura 或 readability-lxml；动态页面用 playwright 兜底）
- 抓取评论区 Top 5（HN/Reddit 都有 API 直接给）
- 可选：搜相关讨论（X、Reddit 交叉搜索），简要总结
- **写出符合 schema 的 source pack 文件**到 `output/packs/YYYY-MM-DD-<slug>.md`

**4. Notify · 通知（可选层，不是关键路径）**

每天产出后发一条日报：「今天发现 X 条候选，详见 output/packs/」。
通知渠道开关式（钉钉 / 邮件 / 本地 macOS 通知 / 不通知），互相独立。
**关键路径是文件，不是通知。** 即使所有通知都关掉，scout 仍然完整工作。

### 关键设计原则

**1. Source pack 是产物，不是中间态**
- 写完即关闭，不再修改（如需重新整理就生成新版本）
- 文件名包含日期 + slug，便于人脑索引
- 即使没有 advocate-agent，pack 自身也是一份「整理好的资料卡」，能直接喂给 Claude.ai 或自己阅读

**2. 严格遵守 schema**
- 写文件前必须用 schema 校验（可用 pydantic / zod）
- schema 变更必须同步 advocate-agent 项目的副本

**3. 去重不是去同质**
- 同一 URL 不再处理（用 SQLite 记录 URL hash + ETag）
- 但同一话题的不同视角（A 篇说 X，B 篇反驳 X）应该都保留——这恰恰是布道者最爱的素材

**4. 可手工注入**
- 提供 `scout pack <url>` 命令：手动指定一个 URL，让 scout 走 Harvest & Pack 阶段，跳过 Discover/Score
- 这样我刷推时看到一篇好文章，可以直接命令行喂给 scout，让它整理成 pack

### 简化原则（明确不做什么）

参考但**不复刻** TrendRadar（github.com/sansan0/TrendRadar，46k stars）。它要照顾几十种使用场景才那么重。我们：

| 维度 | TrendRadar | 我们 |
|------|-----------|------|
| 平台 | 11+RSS | HN + GH Trending + Reddit（V0.1） |
| 推送渠道 | 8 个 | 1-2 个，且非关键路径 |
| 部署 | Docker + Actions + S3 | 本地 cron + SQLite |
| LLM | 100+ provider via LiteLLM | 仅 Anthropic Claude |
| 翻译/独立展示/MCP/Web 编辑器 | 有 | 不做 |
| 输出 | 推送消息 + HTML 报告 | 标准化源文件（核心） |

**目标代码量**：< 2000 行 Python。

### 产品形态

#### CLI（核心）
- `scout discover` — 跑一次完整的发现+筛选+打包流程
- `scout pack <url>` — 手动喂一个 URL，整理成 pack
- `scout list` — 列出近期 pack 文件
- `scout show <pack-id>` — 查看 pack 详情
- `scout score-tune` — 用历史样本调试评分提示词

#### Cron / 定时
本地 crontab 或 systemd timer，每天 2-3 次。不需要复杂调度系统。

#### Web
**V0.1 不做**。文件系统 + CLI 已经够了。如果未来要做，目标是「pack 浏览器」，而不是配置编辑器。

### 技术栈

不要直接选型。给 1-2 个候选方案让我评审。
我倾向 Python（更适合写爬虫、抓取、数据处理）。
LLM：Anthropic Claude（已有 API key）。

### 你的第一步：规格先于代码

不写任何业务代码。先完成：

**1. 完整读完 `docs/source-pack-schema.md`** 和 `docs/upstream-context.md`，确保你理解输出契约。

**2. 产出 `docs/specification.md`：**
- 三阶段流水线的数据流图（mermaid）
- 关键数据模型（candidate / pack / dedup record）
- CLI 命令清单 + 使用示例
- 关键词配置文件格式
- 评分提示词的版本化策略

**3. 产出 `prompts/scoring.md` 的 v0 草案：**
- 系统提示词
- 输入格式 + 输出格式
- 至少 3 个 few-shot 示例（高分 / 中分 / 低分各一个）
- 用我的真实选题历史校准（我会提供）

**4. 产出 `docs/architecture-options.md`：** 1-2 个候选方案 + 推荐。

**5. 创建 `CLAUDE.md`** 作为项目长期记忆：愿景 / 与 advocate-agent 的契约纪律 / 不做清单 / 决策日志。

完成以上五步后停下来等我评审。

---

## 立项 checklist（advocate 维护方查阅）

立项 scout-agent 时务必：

- [ ] cp 本 advocate repo 的 `docs/source-pack-schema.md` 到新 repo 同路径
- [ ] 在新 repo 创建 `docs/upstream-context.md`，简要描述 advocate 的 P1-P6 工作流（让 scout 知道下游怎么用 pack）
- [ ] 在 advocate repo 启用 schema hash 双向比对的 CI（详见 advocate `docs/source-pack-schema.md` §6）
- [ ] 把 advocate `tests/fixtures/example-pack/` 的 manual + scout 两个 fixture 也 cp 一份过去
