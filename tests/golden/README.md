# Golden tests

每次改 phase / prompt / model 之前先跑这里。

## 怎么跑

```bash
pytest tests/golden/
```

## 怎么更新

变更确实合理时：

```bash
pytest tests/golden/ --update-golden
```

更新前必须人工审视 diff，确认不是质量退化。
