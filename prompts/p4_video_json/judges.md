# P4 Judge Prompts

3 项共同红线 judge gate（与规则 gate 共同构成 §5.3.0）。

## P4_first_sentence_complete

```
hook scene 的 main_text 第一句: "{{ first_sentence }}"

判断这是不是一个完整的中文句子（主谓齐全 / 表达独立完整），
而不是一个孤立的冲击词 + 停顿（如"封杀。"、"920倍。"等）。

- 完整句子（即使短）→ passed=true
- 孤立词 / 数字 + 句号 + 看似要等观众等下一句 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P4_judgment_exists

```
P2.5 核心判断: "{{ judgment_full_sentence }}"

视频所有 scenes 的 tts_text 拼接（截前 4000 字）:
"""
{{ all_tts_text }}
"""

判断这个 P2.5 核心判断的**本质内容**是否在视频中体现了。

- 不要求逐字一致；意思一致即可（"X 不是 Y, 而是 Z" 与 "Y 没死，X 才是真相"
  这种结构同义 → passed=true）
- 视频里完全没有提到判断的核心信息 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```

## P4_oral_friendly

```
随机抽取的 tts_text 段（最多 1500 字）:
"""
{{ tts_sample }}
"""

判断整体是否口播友好：
- 无大量自问自答（"你以为 X？其实是 Y"过多）
- 无书面语（"综上所述"、"由此可见"等）
- 无生硬抽象概念堆砌
- 句子可以被人自然念出

满足整体可念 → passed=true；显著不口播友好 → passed=false。

返回 JSON: {"passed": bool, "rationale": "..."}
```
