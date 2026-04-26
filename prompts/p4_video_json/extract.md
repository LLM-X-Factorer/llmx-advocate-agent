# P4 — Video JSON Generation

> Source: VIDEO_JSON_REFERENCE.md + BILIBILI_WORKFLOW.md §3-4 + SKILL.md.
> 输出符合视频渲染系统 schema 的完整 JSON。

## ⚠️ OUTPUT LANGUAGE: 中文

所有 `tts_text` / `title` / `main_text` 等字段必须中文。仅 scene_type 等枚举值用英文。

## Inputs

- 主题 (P2.6 theme): "{{ theme }}"
- 核心判断 (P2.5 judgment.full_sentence): "{{ judgment_full }}"
- Tier: {{ tier }}
- 目标 scene 数: {{ target_scene_count }}
- 目标总时长: {{ target_duration_seconds }} 秒
- export_formats: {{ export_formats }}
- 开头风格: **{{ opening_style }}**

- 角度（P1.5）: {{ angle.your_position }}
- 上层洞察（P2.6 why_round 摘要）: {{ deep.why_round[:2] }}

- 核心 findings (P3 — 围绕这些组织 content scenes):
{% for f in findings %}
  - {{ f.description }} {% if f.key_data %}（{{ f.key_data }}）{% endif %}
{% endfor %}

- 关键数据: {{ key_data_points }}
- 故事: {{ stories }}
- 金句: {{ quotable_lines }}
- 权威背书: {{ authority_anchors }}

## 严禁出现（违反任一即重写）

- 来源背书：`今天聊一个 HN 热榜的文章` / `刚上 Hacker News` / `最近 XX 很火`
- 搬运工句式：`今天聊一个` / `我来给大家解读` / `今天给大家介绍` / `带大家看看`
- 泛知识博主：`Hey 各位 B 站朋友们` / `各位粉丝大家好` / `Hey各位`
- 孤立冲击词："封杀。"（停顿）"920倍。"（停顿）— 第一句必须是完整句

## 必须做到

- 视频中**必须出现核心判断的核心内容**（不必逐字一致，意思要到位）
- 第一个 hook scene 的 `main_text` 是完整的句子
- 频道介绍**固定**："大家好，这里是LLM-X-Factors，一个专注于拆解大语言模型时代底层逻辑的频道。"
- 结尾**固定**："这里是LLM-X-Factors，我们下期见。"

## 开头风格分叉

{% if opening_style == "judgment_first" %}
**judgment_first 风格**（适合留存 / 转化 / 决策者向）：

```
[scene 1: cover]              ← 视觉封面，无 tts_text
[scene 2: hook]               ← 0-15 秒，亮出核心判断（核心判断必须在 ≤50 中文字符内出现）
[scene 3: channel_intro]      ← 频道介绍（紧随 hook 之后）
[scene 4: hook_support]       ← 数据/事实支撑判断
[scene 5+: chapter_transition + content × N]
[scene N-1: summary]
[scene N: outro]
```

hook 的 `main_text` 必须在前 50 中文字符内包含核心判断的本质。

{% else %}
**suspense_first 风格**（适合引流 / 拉新破圈）：

```
[scene 1: cover]
[scene 2: hook]               ← 0-15 秒，话题 + Hook + 可信度（**不**直接给判断）
[scene 3: channel_intro]
[scene 4: hook_support]       ← 用数据 / 故事铺垫，30-60 秒间让判断落地
[scene 5+: chapter_transition + content × N]
[scene N-1: summary]
[scene N: outro]
```

判断在前 30 秒**不要**说出完整结论；30-60 秒间在 hook_support 或第一段 content 让它落地。
{% endif %}

## Scene 类型速查

| scene_type | 必填字段 | tts_text |
|------------|---------|----------|
| `cover` | title | 无 |
| `hook` | main_text | tts_text 一段 |
| `channel_intro` | main_text | 上面的固定开场白 |
| `hook_support` | title 或 cards | 数据支撑段 |
| `chapter_transition` | chapter_number, chapter_title | 一句过渡 |
| `content` | title, bullets 或 visual | 主体段 |
| `summary` | title | 总结段 |
| `outro` | headline | 结尾固定语 |

## duration 公式

每个有 tts_text 的 scene：
```
duration_seconds = max(5, len(tts_text) / 3.2 + 2)
```

中文口播 ≈ 3.2 字/秒。请按公式自己计算并填入每个 scene 的 `duration_seconds`。

## 输出格式（严格 JSON）

仅返回完整 JSON 对象，无 markdown 围栏，无前后解释。

```json
{
  "export_formats": {{ export_formats }},
  "scenes": [
    {
      "scene_type": "cover",
      "title": "...",
      "subtitle": "...",
      "duration_seconds": 3
    },
    {
      "scene_type": "hook",
      "main_text": "...",
      "duration_seconds": 12,
      "tts_text": "..."
    },
    {
      "scene_type": "channel_intro",
      "main_text": "LLM-X-Factors",
      "sub_text": "拆解大语言模型时代的底层逻辑",
      "duration_seconds": 8,
      "tts_text": "大家好，这里是LLM-X-Factors，一个专注于拆解大语言模型时代底层逻辑的频道。"
    }
  ]
}
```

## ⚠️ 必须达到的输出量

scenes 数组**必须**至少 {{ target_scene_count - 4 }} 个 scene（不要偷懒合并 / 跳过 chapter）。
总时长**必须**接近 {{ target_duration_seconds }} 秒（中间 content 段每个 ≥ 20 秒口播，含具体数据 / 故事 / 对比）。

**完整结构提醒**：
1. cover（1）
2. hook（1）+ channel_intro（1）+ hook_support（1）= 3 个开场
3. chapter_transition × 至少 3 + 每章 content × 3-5 个 = 至少 12-15 个中段
4. summary（1）+ outro（1）= 2 个收尾

合计 ≥ {{ target_scene_count - 4 }} 个 scene 是底线。如果你写出来的 scene 少于此数，请补齐章节内的 content。

每个 content scene 的 tts_text **不少于 60 字**（约 20 秒口播）。
