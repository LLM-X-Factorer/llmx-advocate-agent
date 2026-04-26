# P4 Suspense-First Judge Prompts

5 项 judge gate（spec §5.3.2）。每个针对 hook + 早期 scenes 的 tts_text 与时间窗。

## P4_sf_topic_established

```
开场前 5 秒（约 15 中文字符）的 tts 内容:
"{{ early_tts_5s }}"

判断这一段是否**独立建立了话题**——
即不假设观众看了标题/封面，仅靠开头这几句就能让人知道在讨论什么。

- 话题在前 5 秒已经清晰（受众听完知道接下来要讲什么领域 / 什么问题） → passed=true
- 仅看开头不知道讨论什么、需要标题补全 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P4_sf_hook_strength

```
开场前 15 秒的 tts:
"{{ early_tts_15s }}"

判断 0-15 秒是否**至少命中以下 5 维素材中的 1 项**：
- 数据 / 数字（如 "55%"、"460 万"、"翻倍"）
- 反差 / 转变（之前 X 现在 Y）
- 可独立成立的金句
- 权威背书（人物 / 机构 / 报告）
- 痛点共鸣（具体焦虑 / 错误做法）

至少 1 维明显命中 → passed=true。完全无任何素材锚点 → passed=false。

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P4_sf_credibility_signal

```
开场前 15 秒 tts:
"{{ early_tts_15s }}"

判断开场是否包含**可信度锚点**（让观众觉得"这个频道讲这个有理由听"）：
- 成绩 / 数据成果（"我去年涨粉 200 万"、"我做过 50 个 RAG 项目"）
- 经验 / 时间投入（"我研究了一周"、"做了 3 年"）
- 权威背书引用（直接引用机构 / 人物 / 报告）

任一可信度锚点出现 → passed=true。空洞声明 / 无锚点 → passed=false。

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P4_sf_no_answer_leak

```
开场前 30 秒的 tts:
"{{ early_tts_30s }}"

P2.5 核心判断（最终结论）:
"{{ judgment_full_sentence }}"

判断这 30 秒是否**避免了直接说出最终结论**？suspense_first 风格的关键是
让观众"想看下去"，前 30 秒只能铺垫话题、暗示张力，不应把判断的核心点说穿。

- 前 30 秒只铺垫问题 / 营造张力，没有把判断的关键揭示出来 → passed=true
- 已经把判断核心说明白（观众听完前 30 秒就不需要继续看） → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P4_sf_judgment_landing

```
30-60 秒区间的 tts:
"{{ tts_30_to_60s }}"

P2.5 核心判断:
"{{ judgment_full_sentence }}"

判断这一区间内核心判断**是否落地**——
即 hook_support 或第一段 content 在 30-60 秒间已经把判断的本质说清楚。

- 30-60s 间出现判断核心内容（不必逐字一致，意思一致即可） → passed=true
- 直到第 60 秒结束都没正面表达判断 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```
