# P2.5 — Core Judgment Extraction

> Source: chinese-content-workflow SKILL.md §Phase 2.5 + dbs-deconstruct (Wittgenstein/Austrian).
> Hard rule: this phase MUST produce a one-sentence judgment that passes 4 QA gates (§5.1).
> Failing here doesn't get retried with a "better prompt" — the engine retries with a
> different angle (fallback to P1.5).

## ⚠️ OUTPUT LANGUAGE: 中文 (Chinese)

**所有自然语言输出字段（`surface` / `transition` / `deeper_essence` / `full_sentence` / `override_reason`）必须用简体中文。`seed_relation` 是英文枚举（accept/deepen/override/none），不需要翻译。**
- B 站受众是中文用户；判断必须可以直接口播
- `full_sentence` **硬约束 ≤ 60 个汉字**（约等于 18 秒口播）— 超过即失败重试

## Inputs

- Source pack title: {{ source_pack.source.title }}
- Pack body excerpt:
{{ body_excerpt }}

- Chosen angle (P1.5):
  - core_tension: {{ angle.core_tension }}
  - your_position: {{ angle.your_position }}

- Layer profile (P2):
  - tier: {{ layer_profile.tier }}

{% if source_pack.scout_analysis and source_pack.scout_analysis.judgment_seed %}
- Scout judgment_seed (起点参考，可推翻): {{ source_pack.scout_analysis.judgment_seed }}
{% endif %}

## judgment_seed handling — 三态明确选择

如果 scout 提供了 `judgment_seed`，把它当作**起点**而非定论。你必须在 `seed_relation` 字段里选择三态之一：

1. **`accept`** — 你独立分析后**完全认同种子的结论**。`full_sentence` 用自己的话表达同一个判断，不抄措辞。
2. **`deepen`** — 种子的**主题方向是对的**，但你的视角更精确 / 切入点更锐 / 找到了更结构性的本质。`full_sentence` 在种子主题之上落到一个种子没说清的层次。**`override_reason` 必填**，说明你深化在哪里。
3. **`override`** — 你的分析得到**不同的结论**。`full_sentence` 提出种子之外的判断。**`override_reason` 必填**，说明哪里推翻了种子。

> **关键区分 `accept` vs `deepen`**：
> - 如果你只是把种子换措辞重述 → `accept`
> - 如果你在种子主题之上加了种子没有的结构性洞察（比如指出"原因背后还有原因"、"测试方法本身有偏"、"X 只是表象，真正的 Y 在更深一层"）→ `deepen`
> - 如果种子是"X 比 Y 更重要"，你说的是"其实 X 和 Y 都不是关键，真正决定的是 Z" → `override`

如果**没有 seed**（手工 pack 或 scout 没给）：用 `seed_relation: "none"`，`override_reason: null`。

**4 项 QA 在最终 `full_sentence` 上跑，种子无豁免。**

## 输出格式（严格 JSON）

```json
{
  "surface": "<表面现象，中文，≤30字>",
  "transition": "但其实 / 真正原因是 / 背后是 / 本质上",
  "deeper_essence": "<深层本质，中文，≤30字>",
  "full_sentence": "<一句话核心判断，中文，≤60汉字>",
  "seed_judgment": "<种子原文 / null>",
  "seed_relation": "accept | deepen | override | none",
  "override_reason": "<deepen 或 override 时必填，accept 或 none 时填 null>"
}
```

仅返回 JSON 对象本身，不要 markdown 围栏，不要任何解释。

## SOP 成功案例（参考结构 + 字数）

| 完整判断（≤60 字） | 字数 |
|---|---|
| 不是因为安全漏洞，而是因为它太好用了——好用到动了巨头的命根子 | 28 |
| 很多人只看到省Token三个字就划走了，但我发现这背后是整个Agent开发逻辑的彻底重构 | 38 |
| Alignment的本质不是技术问题，是权力问题——谁的钱多，就对齐谁 | 27 |

## 抽取技巧（任选 / 组合）

1. **"所以呢" 链** — 不停问 so what，直到触及结构性洞察
2. **"和 X 有什么不同"** — 与同类相比，根本差异在哪
3. **"如果我是决策者，我该怎么想"** — 决策者会关心但原文没说的事

## Wittgenstein/Austrian 校准（来自 dbs-deconstruct）

- 伪概念检测：去掉关键词用大白话还能说清吗？说不清→可能是伪概念
- Question vs Problem：是有标准答案的事，还是要实践的事？
- 价格信号：判断能否被市场行为验证？

## 禁止输出

- 复述原文（违反 P2.5_uniqueness）
- 必须看原文才能理解（违反 P2.5_independent_value）
- 超过 60 汉字（违反 P2.5_brevity）
- "今天聊一个 / 刚上 HN 热榜 / 我来给大家解读" 等搬运工短语（违反 P2.5_anti_relay）
- 抽象口号（"X 改变世界"、"Y 是未来"）— 必须有具体的结构性内容

## 最后一步：自检

在返回前**默念 `full_sentence`**：
- 是中文吗？是
- 数过字数 ≤ 60 吗？数清楚
- 不依赖原文也能让人听懂吗？是
- 有具体内容（不是口号）吗？有
