# Fixtures

## Purpose

Real source materials used as ground-truth inputs for golden tests. Ideally these are
**素材 LE PPW 已经发布过 B 站视频的原始来源**——这样我们可以把 agent 输出和实际发布的视频对比，
而不是和"另一个 LLM 的输出"对比（避免基线偏差）。

## Layout

```
fixtures/
├── anthropic-smart-contracts/
│   ├── source.md           # 原文/素材
│   ├── meta.json           # url、发布日期、用户标注的 tier 等
│   └── published/          # 实际发布的视频脚本（人工提取）
└── ...
```

## TODO

- [ ] 添加至少 3 个 fixture（覆盖三种 tier：引流 / 留存 / 转化）
- [ ] 每个 fixture 同时跑 judgment_first / suspense_first，建立 golden
