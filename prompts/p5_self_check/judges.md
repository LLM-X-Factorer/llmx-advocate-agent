# P5 Judge Prompts

裁判型 gate（spec §5.4.3 + §5.5）。

## P5_sync_one_focus

```
Scene 信息:
  - scene_type: {{ scene_type }}
  - visual.type: {{ visual_type }}
  - visual 主要展示内容: {{ visual_summary }}
  - tts_text: "{{ tts_text }}"

判断这一段 tts 是否**只讲画面上能看到的内容**？
即 tts 提到的要点 / 数据 / 主题，画面都有对应展示。

- tts 涉及的要点 / 主题与 visual 一致 → passed=true
- tts 提到了 visual 没有展示的多个要点（如单卡 visual 但 tts 讲多条）→ passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P5_sync_continuity

```
跨 scene 的 tts 拼接（最多 3 个连续 scene）:

[Scene {{ idx_a }} | {{ type_a }}]
{{ tts_a }}

[Scene {{ idx_b }} | {{ type_b }}]
{{ tts_b }}

[Scene {{ idx_c }} | {{ type_c }}]
{{ tts_c }}

判断这 3 段是否口播连贯：
- 不重复引入同一框架（如反复说"三个启示"）
- 后续段落自然续接前面
- 没有突兀跳话题

连贯 → passed=true；显著重复 / 跳跃 → passed=false。

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P5_public_verifiable_language

```
随机采样的 tts_text（≤2000 字）：
"""
{{ tts_sample }}
"""

判断整体语言是否**公共可验证**——
即所有抽象词都能通过具体例子兑现，没有"只有作者自己能理解的私语"。

- 出现明显抽象但无解释的私语 → passed=false
- 抽象概念都有具体例子 / 可验证陈述 → passed=true

返回 JSON: {"passed": bool, "rationale": "..."}
```
