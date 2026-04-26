# Contributing

> 项目当前阶段是**先服务自己（LE PPW）**——外部贡献暂不接收 PR，但欢迎在 Issue 区提建议、报 bug、讨论 SOP。

## 本地开发

见 [README.md](README.md#快速开始)。

## 必须遵守的红线

1. **不要绕过质检**。`--force` 标记不存在，永远不要加。如果一个 gate 太严，先讨论修改 gate，不要绕。
2. **改 phase / gate 标准**，必须先改 `docs/specification.md`，再改实现。
3. **裁判 LLM 永远固定**（settings.LLMX_JUDGE_*），跨 task 稳定不变是底线（评测对比的"不变量"）。当前 V0.1 绑定 `inclusionai/ling-2.6-1t:free`（OpenRouter 免费层），拿到 Anthropic key 后会切回 `claude-opus-4-7`——任何切换必须更新决策日志。
4. **fixture 必须用真实素材**——优先用已发布视频的原始素材，禁止用 LLM 合成的假素材。
5. **prompt 改动等同代码改动**——一定要跑 golden test。

## 提交风格

- Commit message 用英文，简洁（1-2 句）
- 不 amend（除非显式同意）
- 不 force push（除非显式同意）

## 文档约定

- 中文写主文档（README、CLAUDE.md、docs/）
- 英文写代码注释和 commit message
- 项目内部文件路径用绝对路径或 repo-root 相对路径
