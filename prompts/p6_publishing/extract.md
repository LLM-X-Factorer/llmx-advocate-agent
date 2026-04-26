# P6 — Auxiliary Output（标题 / 简介 / 置顶时间戳）

> Source: BILIBILI_WORKFLOW.md §5 + dbs-xhs-title 12 类心理触发器（B 站口味适配）。
> 目标：标题体现核心判断、简介结构清晰、置顶含可点击时间戳。

## ⚠️ OUTPUT LANGUAGE: 中文

所有字段中文。仅 `formula_id` 字段用英文 ID（参考下面的公式池）。

## Inputs

- 主题 (P2.6 theme): "{{ theme }}"
- 核心判断 (P2.5 judgment.full_sentence): "{{ judgment_full }}"
- Tier: **{{ tier }}**
- 关键数据: {{ key_data_points }}
- 金句: {{ quotable_lines }}

- 章节时间戳（已由 Python 计算，**直接使用，不要重算**）：
{% for ts in chapter_timestamps %}
  - {{ ts.timestamp }} — {{ ts.title }}
{% endfor %}

## 标题公式池（按 tier 选择）

{% if tier == "引流" %}
**引流层公式**：
- `liuyin_data` — `[震撼数字] + [这意味着什么]` 例："920倍！AI漏洞发现能力一年暴涨"
- `liuyin_counter` — `[反常识] + [为什么]` 例："AI越强大，程序员越值钱？反直觉的逻辑"
- `liuyin_china` — `[中国视角] + [信息差]` 例："硅谷正在发生什么？国内还没注意到的3个信号"
- `liuyin_hot_take` — `[热点] + [你的判断]` 例："豆包手机被围剿：当 AI 替你刷淘宝，巨头们慌了"
{% elif tier == "留存" %}
**留存层公式**：
- `liucun_path` — `[身份认同] + [路径/方法]` 例："普通人做 AI 产品的正确路径"
- `liucun_judgment` — `[我的判断] + [决策框架]` 例："2025 年 AI 创业还有哪些机会？我的 3 个判断"
- `liucun_recap` — `[案例复盘] + [可复制模式]` 例："我复盘了 5 个 AI 创业失败案例，总结出这个公式"
- `liucun_essence` — `[本质洞察] + [真正原因]` 例："为什么 90% 的 AI Agent 项目都会失败？"
{% else %}
**转化层公式**：
- `zhuanhua_pain` — `[痛点场景] + [解决暗示]` 例："Demo 爽翻上线就崩盘？Agent 怎么救？"
- `zhuanhua_gap` — `[能力缺口] + [系统方法]` 例："从 Demo 到 Production：90% 的人卡在这一步"
- `zhuanhua_funnel` — `[深度内容] + [完整版引导]` 例："RAG 系统设计的 7 个关键决策｜完整框架"
{% endif %}

## 标题硬约束

- 长度 **20-35 中文字符**
- 必须**体现 P2.5 判断的核心张力**（不是单纯主题词的复述）
- 避免过度标题党（不允许 "震惊！" / "你绝对想不到！" 等农场词）
- 包含可搜索的关键词（具体技术 / 产品 / 数字 / 人名）
- 不出现 "今天聊一个 / HN 热榜" 等来源背书

## 简介模板

```
{一句话说明视频核心观点}

{2-3 个核心看点，每条用 emoji 起头：📊 数据 / 🔍 案例 / 💡 洞察}

💬 你怎么看？欢迎讨论。
```

简介总长度 80-200 字。

## 置顶评论模板

```
⏱️ 时间戳：
00:00 开场
{每个章节一行，用上面给的 chapter_timestamps}

💬 看完有什么想法？
```

请直接使用提供的 `chapter_timestamps` 列表，不要自己计算时间。

## 输出格式（严格 JSON）

```json
{
  "titles": [
    {
      "text": "<标题选项 1，20-35 字>",
      "formula_id": "<上面公式池中的 ID>",
      "rationale": "<一句话说明这个标题如何体现判断>"
    },
    {
      "text": "<标题选项 2>",
      "formula_id": "<另一个公式 ID>",
      "rationale": "..."
    }
  ],
  "description": "<视频简介，按上面模板>",
  "pinned_comment": "<置顶评论，含时间戳>"
}
```

`titles` 长度 **2-3 个**。仅返回 JSON 对象，无 markdown 围栏，无解释。
