# P2.6 Judge Prompts

4 项 Depth Test (spec §5.2) — 都是 binary judge gates，返回 {"passed": bool, "rationale": str}。

## P2.6_beyond_surface

```
Theme: "{{ theme }}"

判断这个 theme 是否**超越表面**——
不是"X 很厉害 / 有问题 / 重要 / 强大 / 颠覆"这种形容词式判断；
而是揭示了 HOW 或 WHY 的结构性洞察。

- 形容词式 / 空洞口号 / "X 是未来" / "X 改变世界" → passed=false
- 揭示具体机制、对比、因果、范式 → passed=true

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P2.6_makes_rethink

```
Theme: "{{ theme }}"

判断这个 theme 是否能让读者**重新思考一个原本默认接受的事**。

- 如果 theme 只是确认大家已经知道的事（"AI 越来越强"、"工具会进化"）→ passed=false
- 如果 theme 挑战某个常见假设、暴露盲点、让"原来如此"的反应出现 → passed=true

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P2.6_transferable

```
Theme: "{{ theme }}"

判断这个 theme 是否**可迁移**——
能否套到至少 2 个其他类似但独立的案例 / 行业 / 现象？

- 如果只对当前这一个案例成立、换个场景就不成立 → passed=false
- 如果是结构性观察，举出 2 个其他场景也能用 → passed=true

请在 rationale 里举出至少 2 个迁移场景以证明（不要只说"可迁移"）。

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P2.6_hook_independent

```
Theme: "{{ theme }}"
原素材话题: "{{ source_title }}"

把当前的热点 / 争议 / 震撼数字 / 名人效应等钩子去掉，
theme 是否仍然作为独立的观察成立？

- 失去钩子就垮 → passed=false（hook-dependent）
- 即使去掉钩子，theme 仍然是有价值的结构性洞察 → passed=true

返回 JSON: {"passed": bool, "rationale": "..."}
```
