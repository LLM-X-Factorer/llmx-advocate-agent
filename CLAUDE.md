# LLM-X Advocate Agent — Claude 项目记忆

> 给未来接手的 Claude 看的项目长期上下文。新会话开始时**首先读这份文件**，然后按需读 `docs/specification.md` 和 `docs/architecture-options.md`。

---

## 1. 项目愿景

把一套**已经验证有效的「AI 工程布道者内容生产 SOP」**封装成 agent 服务。

- **使用者**：LE PPW（AI 工程布道者，B 站频道 LLM-X-Factors）
- **第一目标**：先服务他自己（先把"把 SOP 跑稳"作为唯一成功标准）
- **未来可能性**：开放给其他创作者（V1.0+ 之后才考虑，不要在 V0.x 阶段为此付出复杂度）

输入：URL / PDF / 话题描述
输出：B 站视频脚本（Video JSON，供自动渲染系统消费）+ 发布配套（标题、简介、标签）

形态优先级：**CLI（V0.1 主战场）** > Web 只读详情页（V0.2） > Web 可交互（V0.3 以后）

---

## 2. 核心理念红线（永远不可妥协）

> 这些是把 SOP 翻译成 agent 时**必须保留**的东西。任何让 agent 退化为"信息搬运工"的设计都不可接受。

### 2.1 角色定位

> 「你是有独特判断的分析师，不是信息搬运工。」

- **频道 slogan 已从「抹平大语言模型时代信息差」改为「拆解大语言模型时代的底层逻辑」** — 这是定位升级的标志，所有内容都要服务于"拆解"，不是"传递"。

### 2.2 P2.5 核心判断 — 4 项强制质检

任何视频都必须先通过 P2.5 的 4 项质检，**没有判断就没有视频**：

1. **独特性**：判断不能是原文已直接表述的内容，必须是你的解读
2. **独立价值**：观众不看原文也能从判断里得到价值
3. **简洁性**：判断必须能在 ≤15 秒内说清（≤50 字）
4. **反搬运**：去掉 "今天聊一个 HN 热榜文章" 这种来源背书后，内容仍然成立

> 这 4 项在 `docs/specification.md` §5.1 已经形式化为引擎层强制门禁——不是 prompt 提醒，是 gate 阻塞。**人工 override 也必须通过质检，不允许 `--force`**。

### 2.3 开头规则（B 站视频）

> **2026-04-26 调整**：原 chinese-workflow 的"判断 15s 前置"是单一红线。LE PPW 反馈 B 站流量瓶颈说明此规则未必最优。开头风格从单一红线降级为可配置实验维度（`opening_style: judgment_first | suspense_first | auto`）。

**真红线（不论风格，永远不可妥协）**：
- P2.5 必须产出有效判断（4 项 QA）——判断**存在性**是不变量
- 视频内必须出现该判断（gate `P4_judgment_exists`）——判断**必须落地**
- 禁止孤立冲击词（"封杀。"+停顿）
- 禁止来源背书（HN/热榜/最近很火）
- 禁止搬运工句式（"今天聊一个..."、"我来给大家解读"）
- 禁止泛知识博主开头（"Hey 各位 B 站朋友们"）
- 第一句必须完整句子

**已降级为风格变量（不再是红线）**：
- 判断在视频中出现的位置（judgment_first：15s 内 / suspense_first：30-60s 落地）
- 详见 `docs/specification.md` §5.3

### 2.4 反 AI 模板写作

参见 `docs/source-skill/extracted/chinese-content-workflow/SKILL.md` 的 "Anti-Template Writing" 段落。**机械的「第一...第二...第三」+ 套路化标题 + 平行加粗块 = AI 味**，是质量第一杀手。

### 2.5 TTS-Visual 同步（Video JSON 层）

观众看到的画面 = 听到的 TTS。不允许 visual 是单卡片但 TTS 讲多个要点。详见规格 §5.4.3 的 6 条规则。

### 2.6 上下游解耦：source pack 是契约，不是建议

> 2026-04-26 架构调整。

- 本项目**不抓 URL、不读 PDF、不搜话题**。这些是 `llmx-scout-agent`（独立项目）的职责。
- advocate-agent 的输入恒为 **source pack 文件**（markdown + YAML frontmatter，schema v1.0）。schema 见 `docs/source-pack-schema.md`。
- scout 缺位时，LE PPW 手工写 pack 也能直接喂下游——这才是干净的接口。
- **`scout_analysis.judgment_seed` 是种子，不是命令**。P2.5 必须能推翻种子（通过 `Judgment.overrode_seed=True`）。即便沿用种子，4 项 P2.5 QA 也照跑——防止 scout 出错污染下游。
- schema 变更必须同步两个 repo（hash 比对 CI）。任何隐式漂移视为契约违反。

---

## 3. 当前阶段

**阶段：phase 主线推进中（P1 / P1.5 / P2 已实现，P2.5 下一步）**

- ✅ 完成：完整阅读 `docs/source-skill/` + `~/.claude/skills/dbs-*` 套件
- ✅ 完成：`docs/specification.md` v0.2（dbs-* 整合 + opening_style 分叉 + scout 解耦）
- ✅ 完成：`docs/architecture-options.md` v0.2（锁定 B+）
- ✅ 完成：项目骨架（pyproject / docker-compose / CI / alembic / prompts 目录）
- ✅ 完成：数据模型 + 状态机引擎（含重试/回退/分叉，单元 + 集成测试覆盖）
- ✅ 完成：持久化层（Postgres + MinIO，aiosqlite 测试不依赖 docker）
- ✅ 完成：LLM provider 抽象（Anthropic + OpenRouter），真验证 DeepSeek-chat / R1 / Ling 1T
- ✅ 完成：质检 gate 框架 + 裁判 LLM 模板（裁判固定 Ling 1T）
- ✅ 完成：FastAPI API + Click CLI（rich 输出，端到端 smoke 通过）
- ✅ 完成：**P1** Source Pack 加载 + 校验（schema + body 长度 + section header 三 gate）
- ✅ 完成：**P1.5** Topic Angle Discovery（LLM 生成 + community signal + 反产品发布通报 judge）
- ✅ 完成：**P2** Content Layer Profile（LLM 分类 + 4 项规则 gate：tier-duration / tier-scene / formats / scores）
- ✅ 完成：**P2.5** ⭐ Core Judgment（4 项强制 QA + 可选第 5 项 cognition_gap）
- ✅ 完成：**P2.6** Cognitive Deepening（三轮追问 + 4 项 Depth Test + theme 字段）
- ✅ 完成：**P3** Core Information Extraction（5 维素材丰富度 + findings 数量约束 + 选题受众面）
- ✅ 完成：**P4** Video JSON Generation（共同 6 红线 + judgment_first 3 项 + 结构校验；suspense_first 5 项 judge gate 待 V0.2）
- ❌ 未开始：P5 / P6
- ❌ 未开始：Celery worker 真接入（M2.3）—— 当前 API 同步跑
- ❌ 未开始：评测脚手架（task fork / eval compare）

**测试覆盖**：133 项（unit 120 + integration 13），全过。Lint 干净。

**下一步**：P5 — JSON Self-Check（schema 校验 + 6 条 TTS-Visual 同步 + anti-AI 味检测）。

---

## 4. 决策日志

按时间倒序记录。每次重大决定都要在这里留痕，包括"决定是什么"、"为什么"、"否决了什么"。

### 2026-04-26 — 评审完成，方案锁定 B+

- **决定**：先产出规格文档 + 架构候选，不写业务代码（已交付）
- **决定**：质检关卡作为引擎层强制门禁，不依赖 prompt 自觉
- **决定**：人工修改产出后**必须重过 QA**，不允许 `--force`
- **决定**：裁判 LLM **跨 task 固定不变**（评测基线不漂移），生成侧才是 A/B 变量。V0.1 因 Anthropic key 不可得，绑定 `inclusionai/ling-2.6-1t:free`（OpenRouter 免费层）；获得 Anthropic key 后切 `claude-opus-4-7`
- **决定**：方案 B+ — 极简自研 Python + FastAPI + Celery + Postgres + MinIO
  - 部署：腾讯云 Lighthouse + Docker Compose
  - 否决：LangGraph（依赖偏重、API 演进激进，规格已清晰，自研 ~300 行可达）
  - 否决：TypeScript（V0.2 只读 Web 用不上类型共享收益；Python 在 LLM 编排/prompt 调试上更顺手）
- **决定**：各 phase 重试上限分别配置，默认值见 spec §5.7
- **决定**：QA 关卡重试耗尽**自动回退**，不停下来让人决定
- **决定**：dbs-* 商业化 skill 整合（已完整阅读 dbs-content / dbs-hook / dbs-benchmark / dbs-deconstruct / dbs-xhs-title）：
  - 7 项**补强**已嵌入现有 phase（spec §6.1）
  - **P0 Topic Validation / P7 Commercial Alignment** 占位，V0.1 不实现（spec §6.2）
  - 明确放弃：dbs-benchmark 颗粒度模仿、dbs-content 不代笔原则
- **决定**：开头风格冲突 — 把"判断 15s 前置"从单一红线降级为可配置实验维度
  - 理由：LE PPW 反馈 B 站流量瓶颈说明现有规则未必最优；不能简单推翻（已有验证成功案例），不能简单加悬念（可能退化为搬运工）
  - 解法：`opening_style: judgment_first | suspense_first | auto` 配置化；P2.5 判断**存在性**仍是红线，仅解锁判断**位置**
  - 评测：`task fork` 支持 model × opening_style 二维 A/B
- **决定**：项目要推 GitHub，README + LICENSE + 项目描述都不省略

### 2026-04-26（晚）— 上下游解耦：source pack 文件契约

- **决定**：把"找选题 + 扒原文 + 整理"拆出去，独立成 `llmx-scout-agent` 项目；advocate 只消费 source pack 文件
  - 理由：原 P1 把上游能力和内容生产绑死，演进路径不清；用文件做契约才是干净的解耦——上游缺位时手工攒一个文件也能喂下游
- **决定**：source pack 用 markdown + YAML frontmatter 格式（schema v1.0），schema 文档放 `docs/source-pack-schema.md`，未来两个 repo 各放一份完全相同副本，CI hash 比对同步
- **决定**：`scout_analysis.judgment_seed` 是种子不是命令——P2.5 可推翻；推翻路径在 Judgment 模型里显式表达（`overrode_seed` / `override_reason`），不是异常分支
  - 理由：scout 出错不能污染下游；4 项 P2.5 QA 在沿用种子时也照跑
- **决定**：先建下游（advocate）后建上游（scout）。scout 启动 prompt 已存档：`docs/future-projects/scout-agent-bootstrap.md`
  - 理由：scout 的产出格式必须满足 advocate 的真实需要，反过来设计容易跑偏
- **决定**：V0.1 阶段 advocate 的 SourceInput 简化为 `pack_path` / `pack_content` 二选一，不再支持 URL/PDF/topic
- **决定**：schema 字段必需性 — `scout_analysis` 整段 optional（手工 pack 不强制写）；`source` + `body` 是 required
- **决定**：V0.1 一个 task = 一个 pack（不支持跨 pack 合并）

### 2026-04-26（更晚）— P1 业务接通（M1）

- **完成**：P1SourcePack.run 接 source_pack_loader（路径 / 内容两种来源）
- **完成**：P1 三项 QA gate（body 非空 / 长度 ≥100 字 / 至少一个 markdown 标题）
- **完成**：8 项 P1 单测（含 happy path / schema 失败 / QA 失败三种路径）
- **完成**：`scripts/demo_p1.py` — in-memory 跑 P1 demo，遇 stub phase 自动停下
- **决定**：MIN_BODY_CHARS = 100（足以排除 stub pack，又不会卡掉简短但有效的 pack）
- **决定**：P1 schema 校验失败用 `InvalidSourcePackError` 而非 QA gate——schema 错就是输入数据错，应该任务直接 fail，不进 QA 重试循环
- **暂缓**（M2 等 review）：DB 持久化、Celery worker 状态机循环、API 真接通、CLI 调 API。在此之前 demo_p1.py 是唯一"端到端"运行通道

### 2026-04-26（夜）— M2.1 + M2.2 完成：DB + API + CLI 端到端

**M2.1：store + engine 主循环（in-process）**
- 完成：`store/repo.py` 异步 CRUD（task / phase_run / human_edit）
- 完成：`engine.run_task_until_blocked()` 状态机主循环（QA 通过/失败/重试/fallback/stub-pause/error 全分支）
- 完成：4 项集成测试（happy / schema fail / qa retry-exhaust / list）
- 决定：output 暂全 inline 入 JSON 列；blob 阈值（store/blob.py 16KB）留待大产出 phase
- 决定：lifespan 自动 `metadata.create_all`（idempotent，保留 alembic 用于未来 schema 演进）

**M2.2：API + CLI 真接通**
- 完成：API 接通 — POST /tasks（create + run）、GET /tasks、GET /tasks/{id}、POST /actions/run、POST /actions/pause、GET /phases/{phase}
- 完成：9 项 API 集成测试（用 ASGITransport + dependency_overrides，无需起 server）
- 完成：CLI httpx 客户端 — task new / list / show / run / pause / resume，rich 表格输出
- 完成：手动 smoke test — uvicorn + sqlite + CLI 端到端跑通，P1 通过 → P1.5 stub paused
- 决定：加 `LLMX_DATABASE_URL` 环境变量 override（本地 dev 用 SQLite，生产 docker 走 postgres_*）
- 决定：CLI 是 API 瘦客户端 — 不直连 DB，API 不可达时给"启动 API"提示
- 决定：API "POST /tasks" 同步跑 `run_task_until_blocked` 直到 paused/done — V0.1 任务短，HTTP timeout 不是问题；M2.3 接 Celery 时改为异步触发
- 决定：B008 (FastAPI Depends in defaults) 在 api/routes/** 加 per-file 忽略 — 这是 FastAPI canonical 用法，ruff 误报
- **暂缓**（M2.3）：Celery worker 接入 — 当前 API 同步跑 task；接入后 POST /tasks 立即返回 task_id + 后台 Celery 任务推进
- 测试覆盖：44 项（unit 31 + integration 13），全过

### 2026-04-26（夜·后）— C: LLM provider 真验证

- 完成：`scripts/verify_llm.py` — 支持 `--check-only` / `--execute` / `--providers anthropic,openrouter`
- 完成：OpenRouter / DeepSeek-chat 真调通过（2.31s，17 in / 25 out tokens，中文响应正确）
- 完成：OpenRouter / DeepSeek-R1（reasoning）真调通过（10.36s，24 in / 312 out tokens；输出 token 含 reasoning，符合预期）
- **未做**：Anthropic 真调验证 — 待 Anthropic key 配好（`.env` 里 ANTHROPIC_API_KEY 当前空）
- 决定：脚本接受 `--providers` 子集，便于单独 debug 某个 provider
- 安全提示已记录：OpenRouter key 在早期评审聊天里暴露，用户后续会 revoke + 重新生成。新 key 写入本地 `.env`（gitignored）即可。**任何 commit / 文档都不要含真实 key 的任何片段**

### 2026-04-26（夜·更后）— B：P1.5 业务接通（第一个真用 LLM 的 phase）

- 完成：`prompts/p1_5_angle/extract.md` Jinja2 prompt，输入 source pack 信息（含 scout_analysis）
- 完成：`prompts/p1_5_angle/judges.md` — `P1.5_not_product_announcement` 裁判模板
- 完成：`core/prompts.py` — Jinja2 渲染器（StrictUndefined 防止字段拼错），prompt 文件按模板路径 `<phase>/<file>.md` 组织
- 完成：`core/qa/judges.py` — 加 `judge_with_template(ref, **ctx)` 接口（template_ref 形如 `p1_5_angle/judges.md#GATE_ID`）
- 完成：`P1_5Angle.run()` — 调生成 LLM (provider+model 从 TaskConfig)，rebuild prompt with body excerpt（≤6KB），parse JSON（容错 fence + bare braces），返回 Angle
- 完成：`P1_5Angle.qa()` — 2 个 gate：
  - `P1.5_has_community_signal`（rule）— pack 必须含 controversy_signals 或 body 含"评论/讨论"段
  - `P1.5_not_product_announcement`（judge）— 裁判 LLM 二值判定
- 完成：12 项单测 + 集成测试更新（mock_llm autouse fixture）
- 完成：**真实端到端 smoke** — uvicorn + sqlite + OpenRouter/DeepSeek-chat 全栈跑通：P1 0ms passed → P1.5 55s passed (2/2 QA) → P2 stub paused
- 决定：让 `TaskConfig.llm_provider` / `llm_model` 默认值动态从 settings 读取（`Field(default_factory=...)`），CLI 不传时也会用 env 配置的 provider
- 决定：`llm_provider` 字段从 `Literal["anthropic","openrouter"]` 改为 `str`——便于未来 provider 扩展，不强制改 model
- 决定：prompt 模板按 `prompts/<phase_id>/<purpose>.md` 组织；`extract.md` 是生成 prompt，`judges.md` 含多个 `## GATE_ID` 段
- 观察：DeepSeek-chat 生成 + 裁判合计 55s（生产 Claude 估计 5-15s）；输出质量看起来真实可用，把 scout controversy_signal 与 judgment_seed 合理融合，未退化为复述
- 测试覆盖：56 项（unit 43 + integration 13），全过

### 2026-04-27（凌晨）— 裁判 LLM 切换 + B': P2 业务接通

**裁判 LLM 切换（架构调整）**
- 用户反馈拿不到 Anthropic key，裁判 LLM 从 Anthropic Claude → OpenRouter `inclusionai/ling-2.6-1t:free`
- 红线本质（裁判跨 task 稳定不变）保留；这是绑定 model 的临时切换，不是放弃"裁判固定"原则
- 真验证 Ling 作裁判：1.69s 响应 + JSON 输出合规 + 二值判断到位（rationale 引用具体短语证明）
- 同步更新：`settings.py` 默认值、`.env.example`、`docs/specification.md` §8、`docs/architecture-options.md` §0 + §4 + §6、`README.md`、`CONTRIBUTING.md`

**P2 业务接通**
- 完成：`prompts/p2_layer/extract.md` — tier + 6 维特性评分 + 时长/场景数/导出格式
- 完成：`P2Layer.run()` — 调生成 LLM（temperature=0.4，分类不需要创意）
- 完成：`P2Layer.qa()` — 4 个规则型 gate：
  - `P2_duration_matches_tier`（按 tier 的合理范围校验）
  - `P2_scene_count_matches_tier`
  - `P2_export_formats_set`
  - `P2_scores_in_1_to_5`
- 完成：14 项 P2 单测 + 集成测试更新
- 完成：**真实端到端 smoke** — 全栈跑通：P1 (0ms, 3/3) → P1.5 (33s, 2/2) → P2 (28s, 4/4) → P2.5 stub paused
- 决定：P2 的 4 个 gate 全部规则型（不调裁判 LLM）——分类是结构化任务，规则校验已足够
- 观察：LLM 把 scout 建议的"留存"推翻成"引流"——符合反污染防线（spec §6.2 / §7.4），advocate 独立判断
- 测试覆盖：70 项（unit 57 + integration 13），全过

### 2026-04-27 — P2.5 业务接通（SOP 红线 phase）

- 完成：`P2_5Judgment.run()` — 5KB body excerpt + Jinja prompt（强制中文输出 + ≤50 字硬约束 + SOP 成功案例 few-shot + Wittgenstein/Austrian 校准）
- 完成：`P2_5Judgment.qa()` — **5 个 gate**：
  - `P2.5_brevity`（rule，≤50 汉字 ≈ 15 秒口播）
  - `P2.5_anti_relay_rule`（rule，黑名单短语扫描）
  - `P2.5_uniqueness`（judge，是否复述原文）
  - `P2.5_independent_value`（judge，不看原文是否成立）
  - `P2.5_anti_relay_judge`（judge，去掉来源背书后是否多余）
  - `P2.5_cognition_gap`（可选第 6 个，`enable_cognition_gap_check=True` 时启用）
- 完成：judgment_seed 处理 — _parse_judgment 在 LLM 没回声 seed 时自动从 pack 填回
- 完成：fallback 链 — P2.5 重试耗尽后回 P1.5 换角度（spec §5.7）
- 完成：15 项单测覆盖 5 类场景（parsing seed / no seed / override / brevity / anti-relay rules / 5-gate 组合 / 6 gate with cognition_gap / 各种失败路径）
- 完成：集成测试 mock_llm 加 P2.5 / judgment_response，期望更新到卡 P2.6 stub
- **修复**：`judge_with_template` 实现 — 之前先 render 整个 judges.md 文件再 extract，导致非目标 gate 的 Jinja 变量也被 StrictUndefined 强求；改为先 extract section 再 render 该 section
- **观察**：真实端到端 smoke 因 OpenRouter free tier rate limit (429) 受阻：
  - P2.5 一个 attempt 涉及 1 生成 + 4 判 = 5 次 OpenRouter 请求；retry 5 次 + fallback 后重跑 = 累计~30 次/分钟，撞 free tier 上限
  - **缓解 1**：OpenRouter adapter 加 429 retry（最多 3 次，指数退避，尊重 Retry-After）
  - **缓解 2**：早期 prompt 让 LLM 用英文输出 → 113 字符 brevity 失败；强制中文输出 + 硬约束后预计大幅降低 retry 频次
  - **未解决**：免费层日限额已被多次 smoke 累计撞穿；一段时间后才能再 smoke。Unit + integration 已 100% 覆盖业务逻辑正确性
- 决定：当 PhaseRun 因 exception 失败时，把错误信息和 traceback 存入 `output._error / output._traceback`，方便事后追溯（V0.2 应该改为正式的 PhaseRun.error_message 字段）
- 测试覆盖：85 项（unit 72 + integration 13），全过

### 2026-04-27 — P2.6 业务接通（Cognitive Deepening）

- 完成：DeepThinking model 加 `theme: str` 字段（P2.6 给后续 phase 的唯一交付物）
- 完成：`prompts/p2_6_deepening/extract.md` — 三轮追问（WHY / MEANING / Validation）+ theme 输出 + 4 项 Depth Test 自检 + 反面示例
- 完成：`prompts/p2_6_deepening/judges.md` — 4 项 Depth Test 裁判模板
- 完成：`P2_6Deepening.run()` — 调生成 LLM (temperature=0.6)
- 完成：`P2_6Deepening.qa()` — **6 个 gate**：
  - `P2.6_theme_brevity`（rule，≤50 汉字）
  - `P2.6_beyond_surface_rule`（rule，黑名单形容词扫描："很厉害/很重要/改变世界/是未来"等）
  - `P2.6_beyond_surface_judge`（judge，结构性洞察 vs 形容词式）
  - `P2.6_makes_rethink`（judge，能否挑战默认假设）
  - `P2.6_transferable`（judge，能否套用到至少 2 个其他场景，rationale 必须举例）
  - `P2.6_hook_independent`（judge，去掉热点钩子后 theme 仍成立）
- 完成：fallback 链 — P2.6 重试耗尽 → 回 P2.5（种子判断本身可能太浅）
- 完成：13 项 P2.6 单测 + 集成测试更新（mock 加 deepening_response，期望卡 P3 stub）
- 测试覆盖：98 项（unit 85 + integration 13），全过

### 2026-04-27 — P3 业务接通（Core Information Extraction + 5 维素材丰富度门）

- 完成：CoreInfo model 扩展 — 加 `quotable_lines / authority_anchors / pain_points` 三个字段（对应 dbs-hook 5 维中的金句 / 权威 / 痛点维度，前两维是 key_data + stories）
- 完成：`prompts/p3_extract/extract.md` — 5 维分类提示 + findings 3-5 条约束 + 中文输出
- 完成：`prompts/p3_extract/judges.md` — `P3_topic_breadth` 受众面裁判
- 完成：`P3Extract.run()` — 调生成 LLM (temperature=0.5)，max_tokens=1500（输出量大）
- 完成：`P3Extract.qa()` — **4 个 gate**：
  - `P3_findings_count_in_range`（rule，3-5 条）
  - `P3_findings_have_data`（rule，每条 finding 必有 key_data 或 source）
  - **`P3_material_richness`** ⭐（rule，5 维至少 3 维非空——dbs-hook 补强 spec §5.6）
  - `P3_topic_breadth`（judge，tier=转化时跳过——付费内容受众本就该窄）
- 完成：fallback = None — P3 失败说明上游 phase 输出对接不上，不能简单回退；任务直接 fail（V0.1 决定）
- 完成：15 项 P3 单测 + 集成测试更新（mock 加 extract_response，期望卡 P4 stub）
- 决定：tier=转化时跳过 topic_breadth gate — 转化层本来就服务窄受众群体，宽广度反而是反向信号
- 测试覆盖：113 项（unit 100 + integration 13），全过

### 2026-04-27 — P4 业务接通（Video JSON Generation）— 第 1 步

- 完成：`prompts/p4_video_json/extract.md` — 完整 video JSON 生成 prompt，含 opening_style Jinja 分支（judgment_first / suspense_first）；强制中文 tts；锁定频道介绍/结尾固定语；列出严禁与必须做到
- 完成：`prompts/p4_video_json/judges.md` — 3 项共同红线 judge：first_sentence_complete / judgment_exists / oral_friendly
- 完成：`P4VideoJSON.run()` — temperature=0.6 + max_tokens=6000（输出量大）
- 完成：`P4VideoJSON.qa()` — **12 个 gate**（共同红线 6 + 结构 4 + judgment_first 2）：
  - 共同红线（rule）：`P4_no_source_backing` / `P4_no_relay_phrases` / `P4_no_pan_kol_opening`
  - 共同红线（judge）：`P4_first_sentence_complete` / `P4_judgment_exists` / `P4_oral_friendly`
  - 结构（rule）：`P4_scene_count` / `P4_total_duration` / `P4_per_scene_duration` / `P4_opening_structure`
  - judgment_first（rule）：`P4_jf_judgment_within_15s`（前 50 字 char-overlap 校验判断本质）/ `P4_jf_judgment_before_intro`
- 完成：`_resolve_opening_style` — `auto` 时按 tier 决定（引流→suspense_first，其他→judgment_first）
- 完成：20 项 P4 单测 + 集成测试更新（mock 加 video_response，期望卡 P5 stub）
- 推迟到 V0.2：suspense_first 风格的 5 项 judge gate（`P4_sf_topic_established` / `P4_sf_hook_strength` / `P4_sf_credibility_signal` / `P4_sf_no_answer_leak` / `P4_sf_judgment_landing`）—— 需要更精细的时间窗口 LLM 判断
- 决定：`P4_jf_judgment_within_15s` 用 char-overlap ≥40% 作启发式（直接 substring 太脆，judge LLM 太贵）；rationale 记录 overlap_ratio
- 决定：duration 容差 ±3s/scene，总时长 ±30%；scene 数 ±3。这些容差可在 V0.2 调
- 测试覆盖：133 项（unit 120 + integration 13），全过

---

## 5. 关键资源

| 资源 | 路径 | 用途 |
|------|------|------|
| 源 skill 文档 | `docs/source-skill/extracted/chinese-content-workflow/SKILL.md` | 核心工作流定义 |
| B 站详细流程 | `docs/source-skill/extracted/chinese-content-workflow/resources/BILIBILI_WORKFLOW.md` | 阶段划分、开头模式、讲稿模板 |
| Video JSON 规范 | `docs/source-skill/extracted/chinese-content-workflow/resources/VIDEO_JSON_REFERENCE.md` | 输出格式 + JSON Schema + 自检流程（55KB，含完整 draft-07 schema） |
| 选题策略 | `docs/source-skill/extracted/chinese-content-workflow/resources/TOPIC_STRATEGY.md` | 三层内容矩阵、爆款规律、避坑清单 |
| 案例参考 | `docs/source-skill/extracted/chinese-content-workflow/resources/EXAMPLES.md` | 真实成功案例的产出参考 |
| 规格 | `docs/specification.md` | 形式化定义，新会话先读这个 |
| 架构候选 | `docs/architecture-options.md` | 待用户评审 |

> 注意：`docs/source-skill/chinese-content-workflow.skill` 是 zip 包，已解压到 `docs/source-skill/extracted/`。

---

## 6. 工作风格约定

- **响应语言**：中文（用户全局 CLAUDE.md 已声明）
- **长答 vs 短答**：用户偏好短而具体；不要在每次响应末尾写"我刚刚做了什么"的总结
- **不写文档/注释**：除非用户要求；现有的 `docs/` 都是用户明确要求产出的
- **改代码原则**：fix what's asked，不要顺便"改进"周围代码
- **风险动作**：destructive 操作（rm -rf、git reset --hard、npm install 全局）必须先确认
- **MCP 优先**：研究用 perplexity / tavily，浏览器自动化用 chrome-devtools / playwright

---

## 7. 给"未来 Claude"的提示

如果你接手时项目已经进入实施阶段：

1. 先 `git log -20` 看最近改动
2. 读 `docs/specification.md` 的 §5（质检关卡）—— 这是最容易写错的部分
3. 改 phase 实现前先看 `prompts/<phase>.md` 和 `tests/golden/`
4. 加新 gate / 改 gate 标准 → 必须在 specification.md §5 同步更新
5. 涉及"商业化 skill"或"自媒体制作 skill"——先问用户要源文件，不要凭想象

如果用户问"这套 agent 跟 Claude.ai 上跑的 skill 有什么区别"：
- 那个是单次对话依赖 LLM 自觉的形式
- 这个是**带强制门禁的工程系统**：质检失败必然阻塞，所有产出可回放、可对比、可逐 phase 人工干预，可在 Claude / DeepSeek 等不同 LLM 间切换做 A/B
