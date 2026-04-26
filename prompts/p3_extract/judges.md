# P3 Judge Prompts

仅 P3_topic_breadth 是 judge 型，其他 P3 gate 全是 rule 型。

## P3_topic_breadth

```
原素材主题: "{{ source_title }}"
P2.6 theme: "{{ theme }}"
内容层级 tier: "{{ tier }}"

判断这个选题受众面是否过窄。

判断标准：
- 如果 tier 是"转化层"，本来就是给特定付费意向群体的 → passed=true（不要求广受众）
- 否则（tier=引流 或 留存）：
  - 受众宽：普通技术读者 / 通用 AI 从业者能看 → passed=true
  - 受众过窄：仅有 Solidity 智能合约工程师 / 仅 NLP 博士 / 仅特定垂直行业 → passed=false

返回 JSON: {"passed": bool, "rationale": "..."}
```
