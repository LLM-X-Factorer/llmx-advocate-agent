# llmx-advocate-outputs

> AI 工程布道者内容生产 SOP 的**结构化产出归档**。每个 task 一个目录，包含 Video JSON + 标题/简介/置顶 + 核心判断摘要。

由 [`llmx-advocate-agent`](https://github.com/LLM-X-Factorer/llmx-advocate-agent) 自动写入并 push，每天 3 轮（10/16/22）随 scout pack 生产节奏。

## 数据流

```
llmx-scout-agent  → push →  llmx-scout-packs（上游素材）
                                ↓ pull
                        llmx-advocate-agent（跑 9 phase）
                                ↓ push
                        llmx-advocate-outputs（本仓·下游成品）
```

## 目录结构

- `<YYYY-MM-DD>/<task-id>/` — 完成任务的归档
  - `task.json` — 元数据（task_id / source_pack_id / tier / judgment / theme）
  - `summary.md` — 人读摘要（标题候选 / 简介 / 章节）
  - `video.json` — 完整 Video JSON（喂渲染系统）
  - `publishing.json` — 标题/简介/置顶
  - `source-pack.md` — 原 scout pack 的内联拷贝
- `failures/<YYYY-MM-DD>/<task-id>/` — 失败任务的复盘记录
  - `task.json` / `error.md` / `source-pack.md`

完整 schema 见 [llmx-advocate-agent/docs/output-archive-schema.md](https://github.com/LLM-X-Factorer/llmx-advocate-agent/blob/main/docs/output-archive-schema.md)。

## 怎么消费

### 把某天的所有视频 JSON 拉出来

```bash
git clone https://github.com/LLM-X-Factorer/llmx-advocate-outputs.git
cd llmx-advocate-outputs/2026-04-27
ls -la */video.json
```

### 看哪些 task 失败了

```bash
ls failures/$(date +%Y-%m-%d)/*/error.md | xargs -n1 head -5
```

### 用 jq 过滤特定 tier 的成品

```bash
find . -name task.json -path '*/2026-*' \
  | xargs -I {} jq -r 'select(.tier == "留存") | .task_id + " " + .title' {}
```

## 不在仓库里的东西

- 完整 PhaseRun 历史 / token 使用 / 成本（在 advocate DB）
- 中间 phase 输出（P1 / P1.5 / P2 / P3 / P5）— 归档只关心成品

完整数据需要去 advocate Web UI 或 CLI `task show <id>` 查。

## 隐私

私有仓。不应包含个人/商业敏感信息——source pack 的内容来自公开网络（HN / Reddit / GitHub），advocate 的判断是分析输出，但仍按内部资料管理。

## 维护

- 仓库由 `llmx-advocate-agent` 上的 cron 自动 push（`scripts/cron-push-outputs.sh`）
- 不要在本仓库手工编辑文件——会被下次 push 覆盖
- schema 改动走 [llmx-advocate-agent](https://github.com/LLM-X-Factorer/llmx-advocate-agent) 的 PR，本仓库只是消费者
