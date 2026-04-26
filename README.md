# llmx-advocate-agent

> AI 工程布道者的内容生产 agent — 消费**标准化源文件**（source pack：markdown + YAML frontmatter），按一套带强制质检关卡的 SOP，转成 B 站视频脚本（Video JSON）+ 发布配套（标题、简介、置顶评论）。
>
> 上游素材抓取归独立项目 [`llmx-scout-agent`](docs/future-projects/scout-agent-bootstrap.md)（尚未启动），通过 [source pack 文件契约](docs/source-pack-schema.md) 解耦。scout 缺位时手工写 pack 也能直接喂下游。

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## 这是什么

这是一套已经在 Claude.ai 上以 skill 形式跑了数月、内容质量已被验证的「AI 工程布道者内容生产 SOP」的工程实现。把它从「单次会话依赖 LLM 自觉」升级成「带强制门禁的工程系统」：

- **质检失败必然阻塞**——P2.5 核心判断 4 项 QA、P4 开头自检、P5 TTS-Visual 同步等关卡是引擎层硬门，不是 prompt 提醒
- **所有产出可回放、可对比、可逐 phase 人工干预**
- **Claude / OpenRouter (DeepSeek) 等不同 LLM 可一键切换做 A/B**
- **开头风格（judgment_first / suspense_first）作为评测维度**，不再是单一红线

频道：[LLM-X-Factors](https://space.bilibili.com/) — 拆解大语言模型时代的底层逻辑。

## 核心理念（红线）

> **「你是有独特判断的分析师，不是信息搬运工。」**

P2.5 的 4 项强制质检是不可妥协的红线：
1. **独特性**：判断不能是原文已直接表述
2. **独立价值**：观众不看原文也能从判断里得到价值
3. **简洁性**：判断 ≤15 秒说清（≤50 字）
4. **反搬运**：去掉来源背书后内容仍然成立

详见 [docs/specification.md](docs/specification.md) §5.1。

## 工作流（9 个 Phase）

| Phase | 职责 | 关键质检 |
|-------|------|---------|
| P1 | **Source Pack 加载 + 校验** | schema v1.0 校验通过；输入数据错则任务直接 fail（不重试） |
| P1.5 | 角度发现（找争议 / 反常识 / 独特视角） | 至少检索 1 条社区讨论 |
| P2 | 内容层级 + 6 维特性分析 | tier 已确定（引流 / 留存 / 转化）|
| **P2.5** | ⭐ **核心判断提取** | **4 项强制 QA** |
| P2.6 | 三层深度思考（信息 → 思考 → 洞察） | 4 项 Depth Test |
| P3 | 关键信息抽取 | **5 维素材丰富度 ≥ 3**（来源 dbs-hook） |
| P4 | Video JSON 生成 | 开头自检（按 opening_style 分叉） |
| P5 | JSON 自检 | Schema + 6 条 TTS-Visual 同步 + anti-AI 味检测 |
| P6 | 标题 / 简介 / 置顶 | 标题体现判断 |

可选扩展（V0.1 不实现）：P0 选题预诊断、P7 商业化对齐 — 来源于 dbs-* 商业化 skill 套件。

## 架构

```
┌────────────────────────────────────────────────────────┐
│  llmx-scout-agent  （独立项目，未启动）                │
│  数据源采集 → 关键词初筛 → LLM 评分 →                   │
│  原文+讨论完整抓取 → 整理 → 输出 source pack 文件        │
└────────────────┬───────────────────────────────────────┘
                 │  source pack（markdown + YAML frontmatter）
                 │  契约：docs/source-pack-schema.md
                 ▼
┌────────────────────────────────────────────────────────┐
│  llmx-advocate-agent  （本项目）                       │
│                                                        │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐             │
│  │   CLI   │──▶│ FastAPI  │──▶│ Postgres │             │
│  └─────────┘   │   API    │   └──────────┘             │
│                │          │   ┌──────────┐             │
│  ┌─────────┐   │          │──▶│  MinIO   │ (大文本/产出) │
│  │   Web   │──▶│          │   └──────────┘             │
│  │ (V0.2)  │   └────┬─────┘                            │
│  └─────────┘        │                                  │
│                ┌────▼─────┐   ┌──────────┐             │
│                │  Celery  │──▶│  Redis   │             │
│                │  Worker  │   └──────────┘             │
│                └────┬─────┘                            │
│                     │                                  │
│                ┌────▼────────────────────┐             │
│                │ LLM Provider 抽象        │             │
│                │ ─ Anthropic (Claude)     │             │
│                │ ─ OpenRouter (DeepSeek)  │             │
│                └─────────────────────────┘             │
└────────────────────────────────────────────────────────┘
```

技术栈：Python 3.12 / FastAPI / Celery / SQLAlchemy / Pydantic / Click / MinIO / Anthropic SDK。
部署：腾讯云 Lighthouse + Docker Compose。

详见 [docs/architecture-options.md](docs/architecture-options.md)。

## 快速开始

> 状态：M2.2 完成 — CLI / API / DB / engine 端到端可跑。phase 业务仅 P1 完整实现，P1.5 之后的 phase 是 stub（任务在 P1 通过后会进入 paused_for_human 状态等业务实现）。

### 最快试跑（SQLite，无 docker）

```bash
# 1. 准备环境
git clone https://github.com/LLM-X-Factorer/llmx-advocate-agent.git
cd llmx-advocate-agent
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. 起 API（用 SQLite 本地数据库）
LLMX_DATABASE_URL="sqlite+aiosqlite:///./dev.db" \
  uvicorn llmx_advocate.api.main:app --reload &

# 3. CLI 真接通 API
llmx task new tests/fixtures/example-pack/scout-pack-example.md
llmx task list
llmx task show <task_id>
```

预期输出：P1 通过 (3/3 QA)，P1.5 stub 抛错→ task 状态变为 `paused_for_human`。

### 完整 docker 部署（Postgres + Redis + MinIO）

```bash
# 1. 准备环境变量
cp .env.example .env
# 编辑 .env：填入 ANTHROPIC_API_KEY / OPENROUTER_API_KEY；不要设 LLMX_DATABASE_URL

# 2. 启动整套
docker compose up -d

# 3. CLI（默认连 http://localhost:8000）
llmx task new tests/fixtures/example-pack/scout-pack-example.md
```

### CLI 命令

```bash
# 任务生命周期
llmx task new <pack_path>         # 喂一个 source pack 文件路径
llmx task list
llmx task show <id>
llmx task run <id>                # 一直执行到完成或卡住
llmx task pause <id> / resume <id>

# 评测（A/B 对比）
llmx eval fork <id> --model=deepseek/deepseek-v4-pro --opening-style=suspense_first
llmx eval compare <task_a_id> <task_b_id>
llmx eval batch --source=<pack> --models=deepseek/deepseek-chat,deepseek/deepseek-v4-pro \
  --opening-styles=judgment_first,suspense_first
```

## 文档

- [项目记忆 / 红线 / 决策日志](CLAUDE.md)
- [规格说明书](docs/specification.md) — agent 形式化定义、状态机、数据模型、9 phase 详解、所有质检关卡
- [Source Pack Schema v1.0](docs/source-pack-schema.md) — 与 `llmx-scout-agent` 之间的接口契约
- [架构方案](docs/architecture-options.md) — 已锁定 B+
- [源 skill](docs/source-skill/) — 原 chinese-content-workflow skill 文档（zip + 解压副本）
- [scout-agent 启动 prompt](docs/future-projects/scout-agent-bootstrap.md) — 上游项目立项时直接引用

## 开发约束

- ✅ 修改 phase / gate 标准，必须同步更新 `docs/specification.md`
- ✅ 加 fixture / golden test 永远先于改 phase 实现
- ✅ 裁判 LLM 固定（V0.1 用 OpenRouter / `inclusionai/ling-2.6-1t:free`；拿到 Anthropic key 后切 `claude-opus-4-7`），任何切换必须同步决策日志——评测基线不能漂移
- ❌ 不允许 `--force` 跳过质检
- ❌ 不要在没读 `docs/source-skill/` 的情况下改 phase 行为

## 实施进度

| 模块 | 状态 |
|------|------|
| 规格 + 架构评审 | ✅ |
| 项目骨架（pyproject / docker / CI / alembic） | ✅ |
| 数据模型 + 状态机引擎（含重试/回退/分叉） | ✅ |
| 持久化层（Postgres + MinIO，aiosqlite 测试） | ✅ |
| LLM provider 抽象（Anthropic + OpenRouter） | ✅ — OpenRouter 真验证通过（DeepSeek-chat / R1 / Ling 1T） |
| 质检 gate 框架 + 裁判 LLM | ✅ — V0.1 裁判固定 `inclusionai/ling-2.6-1t:free` |
| FastAPI HTTP API + Click CLI（rich 输出） | ✅ |
| **P1** Source Pack 加载 + 校验 | ✅ |
| **P1.5** Topic Angle Discovery（LLM） | ✅ |
| **P2** Content Layer & Characteristic（LLM） | ✅ |
| **P2.5** Core Judgment（4 项强制 QA + 可选第 5 项） | ✅ |
| **P2.6** Cognitive Deepening（4 项 Depth Test） | ✅ |
| **P3** Core Information Extraction（5 维素材丰富度门） | ✅ |
| **P4** Video JSON Generation（共同 6 红线 + judgment_first 3 项 + suspense_first 5 项 + 结构校验） | ✅ |
| **P5** JSON Self-Check（6 条 TTS-Visual 同步 + 5 项 anti-AI 味 + 结构完整性） | ✅ |
| **P6** Auxiliary Output（2-3 个标题 / 简介 / 章节时间戳）| ✅ |
| Celery worker 接入（异步任务推进） | ✅（`run_async=true` opt-in，inline 仍是默认）|
| 评测脚手架（task fork / eval compare / eval batch） | ✅ |
| Web 只读详情页（V0.2） | 🚧 |
| P0 选题预诊断 / P7 商业化对齐 | 🚧 V0.3 之后 |

**🎉 V0.1 完整闭环：真实 scout pack（reddit DeepSeek-v4 inference）经 9 phase 全栈跑通到 COMPLETED**，3.5 分钟产出 22 scenes / 8.2 分钟 B 站视频 JSON + 3 个标题选项 + 简介 + 章节时间戳。golden 输出存档在 `tests/golden/scout-deepseek-v4-pack-video.json`。

测试：188/188 通过。

## 路线图

- [x] V0.0 规格 + 架构评审 + 项目骨架
- [x] V0.1 OpenRouter 接入 + LLM 抽象层验证（DeepSeek-chat / R1 / V4-Pro / V4-Flash / Ling-1T）
- [x] V0.1 P1 → P6 业务全部实现
- [x] V0.1 P4 suspense_first 风格 5 项 judge gate
- [x] V0.1 Celery 异步任务（opt-in via `run_async=true`）
- [x] V0.1 评测脚手架（task fork / eval compare / eval batch）
- [x] V0.1 真实端到端 smoke（scout pack → 9 phase → COMPLETED，3.5 min，golden 输出已存档）
- [x] scout-agent v0.1 schema 同步（接受所有 scout-real 产出）
- [ ] V0.2 只读 Web 详情页
- [ ] V0.3 P0 选题预诊断 / P7 商业化对齐
- [ ] V1.0 对外开放

## License

MIT — 见 [LICENSE](LICENSE)。

## 致谢

核心 SOP 来自 [chinese-content-workflow skill](docs/source-skill/)（LE PPW 在 Claude.ai 上沉淀）。
商业化补强来自 [dontbesilent dbs-* skill 套件](https://github.com/dontbesilent)。
