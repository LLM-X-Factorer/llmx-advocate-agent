# 技术方案 — 已锁定 B+

> **2026-04-26 评审决议**：方案为 **B+（极简自研 Python + FastAPI + Celery + Postgres + MinIO，部署 Lighthouse）**。本文保留历史推导过程供后续审计；实施只看 §3 + §4。
>
> 配套阅读：`docs/specification.md`（规格定义）

---

## 0. 选型轴（已对齐）

下面 5 个维度决定了哪个方案胜出，请先对每个维度给我一个倾向：

| 轴 | 决策 |
|----|------|
| **目标** | 押对长期架构（不为 V0.1 速度妥协） |
| **运行模型** | V0.1 即服务化（API + worker，部署 Lighthouse） |
| **多 LLM 抽象** | V0.1 即支持 OpenRouter（DeepSeek 经此接入） |
| **Web 端形态** | V0.2 只读详情页 |
| **语言** | Python 3.12（LLM 编排生态、prompt 调试、评测脚本最顺手） |

> 我的预判：你在 CLAUDE.md 提到「**先服务自己**」+「**V0.1 主战场是 CLI**」+「LLM 已有 Claude key」，这指向"快速跑通 + 单用户 + 本地存储 + Python"。但你也明确要求"OpenRouter / DeepSeek 对比测试"，所以**多 LLM 抽象这条轴必须现在就解决**——不是 provider 切换的问题，是裁判 LLM / 生成 LLM 双层独立切换的能力。

---

## 1. 候选方案对比

### 方案 A：Python + LangGraph + Click CLI + SQLite（V0.1）→ FastAPI（V0.2）

**技术栈**

| 层 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| Agent 框架 | LangGraph（状态机 + 节点 + checkpoint 内置） |
| LLM 抽象 | LangChain `BaseChatModel` + OpenRouter community provider，或者直接 `litellm` |
| CLI | `click` 或 `typer` |
| HTTP（V0.2） | FastAPI + SSE |
| 存储 | SQLite（V0.1 单文件，~/.llmx-advocate/db.sqlite）→ 升级时迁 Postgres |
| Schema 校验 | `jsonschema`（直接吃 `VIDEO_JSON_REFERENCE.md` 里的 draft-07 schema） |
| 裁判 LLM | 固定 Anthropic Claude（Opus，保证基线） |

**目录结构**

```
llmx-advocate-agent/
├── pyproject.toml
├── src/llmx_advocate/
│   ├── core/
│   │   ├── phases/                # 每个 phase 一个文件
│   │   │   ├── p1_material.py
│   │   │   ├── p1_5_angle.py
│   │   │   ├── p2_layer.py
│   │   │   ├── p2_5_judgment.py    # ⭐ 含 4 项 QA
│   │   │   ├── p2_6_deepening.py
│   │   │   ├── p3_extract.py
│   │   │   ├── p4_video_json.py    # ⭐ 含开头自检
│   │   │   ├── p5_self_check.py    # ⭐ Schema + 6 同步规则
│   │   │   └── p6_publishing.py
│   │   ├── qa/                    # 质检 gate 实现
│   │   │   ├── judges.py          # 裁判 LLM 封装
│   │   │   ├── rules.py           # 规则型 gate
│   │   │   └── gates.py           # gate 注册表
│   │   ├── graph.py               # LangGraph 拼装
│   │   ├── models.py              # Pydantic 数据模型（对应 spec §3）
│   │   └── llm/
│   │       ├── provider.py        # 抽象层：generate(model, prompt)
│   │       ├── anthropic.py
│   │       ├── openrouter.py      # OpenRouter，含 deepseek-v4-pro
│   │       └── judge.py           # 裁判 LLM，固定走 Anthropic
│   ├── store/
│   │   └── sqlite_store.py        # task / phase_run / human_edit 持久化
│   ├── cli/                       # click 命令
│   │   ├── task.py
│   │   └── eval.py                # task fork / eval compare / eval batch
│   └── api/                       # V0.2 FastAPI
│       └── ...
├── prompts/                       # phase 的 prompt 模板（从 SOP 文档提炼）
│   ├── p2_5_judgment.md
│   └── ...
├── tests/
│   ├── fixtures/                  # 评测用的 source 素材
│   └── golden/                    # phase 产出的 golden 输出
└── docs/
```

**Trade-off**

| 维度 | 评价 |
|------|------|
| ✅ 长项 | LangGraph 节点-边模型 1:1 对应规格里的 phase 状态机；checkpoint 内置（重试/恢复几乎免费）；社区里 agent 系统普遍用，资料最多 |
| ✅ 长项 | LiteLLM/LangChain 已有 OpenRouter 接入，多 provider 切换近乎零成本 |
| ⚠️ 风险 | LangGraph API 演进激进，1.x 之前可能要跟着升 |
| ⚠️ 风险 | LangChain 依赖偏重；如果只做 SOP 这一件事，可能"杀鸡用牛刀" |
| ⚠️ 风险 | Python 类型不如 TS 严格；规格 §3 那些 PhaseOutput 多态用 Pydantic 还是要写很多 union |

---

### 方案 B：Python 极简自研 + Click CLI + SQLite（V0.1）→ FastAPI（V0.2）

**技术栈**

| 层 | 选型 |
|----|------|
| 语言 | Python 3.12 |
| Agent 框架 | **不用框架**，自己写一个 200 行的状态机引擎 |
| LLM 抽象 | 直接用 `anthropic` SDK + `httpx`（OpenRouter REST 直调） |
| CLI | `click` |
| HTTP | FastAPI + SSE |
| 存储 | SQLite |
| Schema 校验 | `jsonschema` |
| 数据模型 | Pydantic |

**目录结构**：与方案 A 相似，但 `core/graph.py` 替换为 `core/engine.py`（自研状态机）。

**自研引擎大致形状**

```python
class PhaseEngine:
    def __init__(self, phases: dict[PhaseId, Phase], store: Store):
        ...
    def step(self, task_id) -> PhaseRun: ...    # 推进一步
    def run(self, task_id) -> Task: ...         # 一直推进直到 paused/done
    def replay(self, task_id, from_phase) -> ...
```

每个 `Phase` 的接口：
```python
@dataclass
class Phase:
    id: PhaseId
    fallback_target: PhaseId | None
    qa_max_retries: int = 3
    
    def run(self, ctx: TaskContext) -> PhaseOutput: ...
    def qa(self, output: PhaseOutput, ctx: TaskContext) -> QAResult: ...
```

**Trade-off**

| 维度 | 评价 |
|------|------|
| ✅ 长项 | 代码最少（V0.1 估计 1500-2500 行）；规格 → 代码 1:1，没有任何"框架抽象"挡在中间，调试最快 |
| ✅ 长项 | 没有 LangChain 依赖偏重的问题；只引入真正用到的库 |
| ✅ 长项 | LLM 切换最灵活，因为自己控制每一次调用 |
| ⚠️ 风险 | checkpoint / 流式 / 回退 这些"框架免费给"的能力要自己写（但规格里这部分逻辑本来就清晰，写起来不复杂） |
| ⚠️ 风险 | 之后如果要加并行 phase（比如 P2 和 P1.5 可以并行），自研引擎要扩；LangGraph 直接 fork node |

---

### 方案 C：TypeScript + XState + Commander.js + Prisma/SQLite → Next.js（V0.2）

**技术栈**

| 层 | 选型 |
|----|------|
| 语言 | TypeScript（Node 20+） |
| Agent 框架 | XState（状态机）+ 自研 LLM 调用层 |
| LLM 抽象 | `@anthropic-ai/sdk` + OpenRouter REST（或 `ai` SDK by Vercel） |
| CLI | `commander` 或 `cac` |
| HTTP | Next.js API Routes（V0.2 顺便做 Web 端） |
| 存储 | SQLite + Prisma |
| Schema 校验 | `zod`（甚至可以直接从 zod 生成 spec 里的 Schema） |
| Web | Next.js 15 + React Server Components + SSE/stream |

**目录结构**

```
llmx-advocate-agent/
├── package.json
├── apps/
│   ├── cli/                       # CLI
│   └── web/                       # Next.js (V0.2)
├── packages/
│   ├── core/                      # phase 引擎 + qa
│   ├── store/                     # Prisma + SQLite
│   ├── llm/                       # provider 抽象
│   └── schemas/                   # zod schemas（任务、phase 产出、video JSON）
└── prompts/
```

**Trade-off**

| 维度 | 评价 |
|------|------|
| ✅ 长项 | 类型系统严格，规格 §3 里的 PhaseOutput discriminated union 在 TS 里非常自然 |
| ✅ 长项 | V0.2 上 Web 时，前后端共享同一套 zod schema + 类型，开发速度直接起飞 |
| ✅ 长项 | Next.js + RSC + Suspense 做流式 LLM 输出体验最佳 |
| ⚠️ 风险 | LLM 编排生态没 Python 丰富（LangGraph TS 版有但远没 Python 版成熟）；prompt 工程社区资料以 Python 为主 |
| ⚠️ 风险 | Node 单机长任务管理不如 Python 顺手（V0.2 上服务时要考虑 worker 拆分） |
| ⚠️ 风险 | 你 Python 写得最快，TS 上手会慢半拍——但你写过 NestJS/Next.js，不算冷启动 |

---

## 2. 横向对比

| 维度 | A: LangGraph | B: 极简自研 Python | C: TypeScript |
|------|-------------|-------------------|--------------|
| V0.1 跑通速度 | 中（要熟悉 LangGraph） | **快**（最少抽象层） | 中（要搭 monorepo） |
| 规格契合度 | **高**（state machine 1:1） | **高**（手控所有逻辑） | 高（XState 也是 1:1） |
| LLM 多 provider | **完美**（LiteLLM 现成） | 好（自己写两个 adapter） | 好（Vercel ai SDK 现成） |
| 长期维护成本 | 中（依赖 LangChain 生态变化） | **低**（依赖少） | 中（Node 生态版本累人，但类型救场） |
| V0.2 Web 体验 | 中（要单独搭前端） | 中 | **优**（Next.js + RSC） |
| 类型安全 | 中（Pydantic 够用） | 中 | **优**（zod + TS） |
| 你的写起来速度 | **快** | **快** | 中 |
| 评测/A-B 友好度 | 高（LangSmith 现成） | 高（自己写少） | 中 |

---

## 3. 我的推荐：B（极简自研 Python）+ 关键纪律

**理由**

1. **规格 §1.3 / §5 的逻辑非常清晰**，自己写一遍状态机 + gate engine 估计 500 行内能搞定，比学 LangGraph API 还快。
2. **LangGraph 的最大价值（checkpoint + 流式 + 节点抽象）在你这个场景里没那么强**——你的 phase 是线性的，回退路径写死在规格里，并行需求暂时没有。
3. **多 provider 抽象是必须的**（你明确要做 DeepSeek 对比），但只需要两个 adapter（Anthropic + OpenRouter），自己写 80 行能完事，不需要 LiteLLM/LangChain 这些通用层。
4. **V0.2 上 Web 时**，FastAPI 加 SSE 流式输出体验已经够用，不需要为了 RSC 切语言。
5. **Python 优势**：prompt 调试 / 评测脚本 / Jupyter 探索数据全都顺手，而这些是这个项目占比最大的工作。

**关键纪律**（采纳方案 B 必须遵守）

- **Phase 接口标准化**：所有 phase 实现同一个抽象基类（`run`/`qa`），引擎不感知具体 phase 的语义——这样替换/并行/重排都是局部改动。
- **裁判 LLM 固定 Anthropic Opus**：这是评测的"参考系"。生成侧切 model 时，裁判不能跟着切，否则 QA 标准漂移，对比就失去意义。
- **存储用 SQLite + 文件混合**：结构化字段（task / phase_run 元数据 / qa_result）入 SQLite；大文本（原文、video JSON）落本地文件，PhaseRun 表里只存路径——这样 task 目录可以直接 cp 到别处分享/归档。
- **prompts/ 独立成目录**：每个 phase 的 prompt 是 markdown 文件（不是 Python 字符串），便于 diff、版本化、人工调优。引擎用 `jinja2` 渲染。
- **fixture + golden test 从第一天就有**：在 `tests/fixtures/` 放 3-5 个真实素材源（你已发布过的视频原始素材最理想），在 `tests/golden/` 落标准产出。每次改 phase / 换 model / 改 prompt，先跑 golden diff。
- **Cost / latency 默认埋点**：每个 PhaseRun 必填 token usage + 耗时——做 Claude vs DeepSeek 对比时这是核心数据。

---

## 4. Claude vs OpenRouter（DeepSeek）对比的工程化设计

> 用户在 CLAUDE.md 中明确要求："比对 claude code 的输出和使用 openrouter 作为 provider 选择类似于最新的 deepseek/deepseek-v4-pro 模型来进行比和测试"。

不论选哪个方案，下面这套**评测脚手架**都要在 V0.1 实现（不是 V0.2）。规格 §4.1.1 里的 `task fork` / `eval compare` / `eval batch` 就是这套脚手架的 CLI 出口。

### 4.1 三轴切换

```
                  ┌─────────────────────┐
                  │   生成侧 LLM        │
                  │ ─ Anthropic         │
                  │ ─ OpenRouter        │
                  │   (deepseek-v4-pro) │
                  └─────────────────────┘
                            ×
                  ┌─────────────────────┐
                  │   开头风格          │
                  │ ─ judgment_first    │
                  │ ─ suspense_first    │
                  └─────────────────────┘
                            ↕
                  ┌──────────────────────────────────┐
                  │   裁判侧 LLM（固定，跨 task 稳定） │
                  │   V0.1: OpenRouter /              │
                  │     inclusionai/ling-2.6-1t:free  │
                  │   未来: claude-opus-4-7           │
                  │   （拿到 Anthropic key 后切回）   │
                  └──────────────────────────────────┘
```

**配置粒度**：
- TaskConfig.`llm_model` 只控制"生成侧"
- TaskConfig.`opening_style` 控制开头风格（`judgment_first` / `suspense_first` / `auto`）
- 裁判 LLM 引擎层固定 Claude Opus，**不受 TaskConfig 影响**——保证 QA 基线一致

`task fork` 命令：
```bash
task fork <id> --model=deepseek/deepseek-v4-pro --opening-style=suspense_first
```
同一素材最多可生成 4 个变体（2 model × 2 opening_style）做 A/B。

### 4.2 评测维度（每个 phase 独立采集）

| 维度 | 数据来源 |
|------|---------|
| QA 通过率 | PhaseRun.qa_result.passed_overall |
| 重试次数 | PhaseRun.attempt 最大值 |
| Token 消耗 | PhaseRun.cost.input_tokens / output_tokens |
| 美元成本 | 按 provider pricing 计算 |
| 单 phase 耗时 | PhaseRun.duration_ms |
| 主观质量 | 人工标注（在 `eval compare` 命令里加 prompt 让用户选 A/B/平） |

### 4.3 报告产出

`eval compare <task_a_id> <task_b_id>` 输出：

- 每个 phase 的产出 side-by-side（diff 视图）
- QA 通过率对比表
- 总成本 / 总耗时对比
- 哪些 phase 是显著差异点（建议关注）
- markdown 格式可以直接贴 issue / 内部分享

### 4.4 fixture 的政治正确

评测必须用**用户已经发布过的真实素材**——LE PPW 在 B 站上发布过的视频原素材是最理想的 ground truth。这样：
- "DeepSeek 在 P2.5 提取的判断"能直接和"实际发布视频里用的判断"对比
- 不是和"Claude 的输出"对比（避免基线偏差）

---

## 5. 决定后我会立刻做的事

如果你拍板用方案 B，我会按这个顺序搭骨架（仍然不写业务逻辑，等你二次确认）：

1. `pyproject.toml` + 依赖（anthropic, click, jsonschema, pydantic, sqlalchemy, jinja2, httpx）
2. `src/llmx_advocate/models.py`：Task / PhaseRun / 各 PhaseOutput 的 Pydantic 定义
3. `src/llmx_advocate/store/sqlite_store.py`：CRUD（最小集，配合 alembic 走迁移）
4. `src/llmx_advocate/core/engine.py`：~200 行的状态机引擎
5. `src/llmx_advocate/core/qa/`：gate 注册表 + 一个 demo gate
6. `src/llmx_advocate/llm/`：provider 抽象 + Anthropic adapter（OpenRouter 留 stub）
7. `src/llmx_advocate/cli/task.py`：`task new / show / step` 三个命令先通
8. `tests/fixtures/` 放 1 个素材
9. README + CLAUDE.md 更新决策日志

总量预估：1-2 个工作日内骨架可跑。然后逐 phase 实现 P1 → P6，每个 phase 配 golden test。

---

## 6. 已决策项汇总

| 问题 | 决策 |
|------|------|
| OpenRouter API key | 已有 |
| 存储 | Postgres + MinIO（不用 SQLite） |
| Web V0.2 形态 | 只读详情页 |
| 裁判 LLM | 固定原则不变；当前绑定 `inclusionai/ling-2.6-1t:free`（OpenRouter 免费层，Anthropic key 不可得期间），拿到 Anthropic key 后切 `claude-opus-4-7` |
| dbs-* 商业化 skill | 已读完 5 个，整合方案见 spec §6 |
| 部署 | 腾讯云 Lighthouse + Docker Compose（API/worker/Postgres/Redis/MinIO） |
| 开头风格冲突 | 配置化为 `opening_style`，作为评测维度而非红线 |
