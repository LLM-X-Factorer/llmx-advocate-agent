# P2 — Content Layer & Characteristic Analysis

> Source: chinese-content-workflow SKILL.md §Phase 2 + BILIBILI_WORKFLOW.md §1.2 / §2.2.

## Inputs

- Source pack title: {{ source_pack.source.title }}
- Pack body excerpt:
{{ body_excerpt }}

- Chosen angle (from P1.5):
  - core_tension: {{ angle.core_tension }}
  - your_position: {{ angle.your_position }}
  - why_readers_care: {{ angle.why_readers_care }}

{% if scout_suggested_layer %}
- Scout suggested layer: {{ scout_suggested_layer }} （仅供参考，可推翻）
{% endif %}

{% if previous_tier %}
## ⚠️ 重要：这是 fallback 重判

上次你把 tier 选成 **{{ previous_tier }}**，但下游 P3 受众面校验失败：
**话题对 {{ previous_tier }} 层的受众太窄**。

请重新评估 tier，**不要再选 {{ previous_tier }}**：

- 如果之前选了「留存」→ 受众太窄说明应该选「转化」（专业付费意向群体本来就窄）
- 如果之前选了「引流」→ 受众太窄说明应该选「留存」（深度内容给铁粉）
- 如果之前选了「转化」→ 不应该出现这种情况，但如有可降级到「留存」

直接换 tier，不要再选 {{ previous_tier }}。
{% endif %}

## Decisions to make

### 1. tier (引流 / 留存 / 转化)

| 引流（拉新出圈） | 留存（建信任） | 转化（付费引导） |
|---|---|---|
| 门槛低、热点钩子强 | 决策框架 / 路径指南 | 课程或服务的核心能力展示 |
| 5-8 分钟，15-18 scenes | 8-12 分钟，23-25 scenes | 10-15 分钟，25-30 scenes |
| 目标播放 1万+ | 目标 5千+，高互动 | 精准付费转化 |

判断标准：
- 普通人能懂吗？需要专业背景？→ 不需要 = 引流候选
- 内容主体是「方法/路径/决策框架」？→ 留存候选
- 涉及付费课程或咨询的核心？→ 转化候选

### 2. 6 维特性评分（每项 1-5 分整数）

| dim | 含义 |
|---|---|
| data_impact | 是否有震撼数字 |
| technical_depth | 需要多深的专业背景 |
| narrative_quality | 有没有故事/案例 |
| timeliness | 时效性 / 是否新鲜 |
| authority | 来源权威性 |
| decision_relevance | 对决策者的意义 |

### 3. target_duration_seconds + target_scene_count

按 tier 推：
- 引流：duration 360-480, scenes 15-18
- 留存：duration 480-720, scenes 23-25
- 转化：duration 600-900, scenes 25-30

### 4. export_formats

- 引流 → ["landscape", "portrait"]（多平台拉新）
- 留存 → ["landscape"]（B 站为主）
- 转化 → ["landscape", "square"]（B 站 + 视频号）

## Output schema (JSON, strict)

```json
{
  "tier": "引流" | "留存" | "转化",
  "characteristic_scores": {
    "data_impact": 1-5,
    "technical_depth": 1-5,
    "narrative_quality": 1-5,
    "timeliness": 1-5,
    "authority": 1-5,
    "decision_relevance": 1-5
  },
  "target_duration_seconds": int,
  "target_scene_count": int,
  "export_formats": ["landscape", "portrait", "square"]   // 含其中至少一个
}
```

Output ONLY the JSON object. No markdown fences, no commentary.
