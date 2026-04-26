# Prompts directory

Each phase ships its prompts as Markdown files (Jinja2 templates), not Python strings, so:

- `git diff` shows prompt changes clearly
- prompts can be reviewed without reading code
- LE PPW can edit them without touching engine code

## Layout

```
prompts/
├── p1_5_angle/
├── p2_layer/
├── p2_5_judgment/
│   ├── extract.md       # generation prompt
│   └── judges.md        # judge prompts for §5.1 gates
├── p2_6_deepening/
├── p3_extract/
├── p4_video_json/
└── p6_publishing/
```

## Convention

- One generation prompt per phase: `extract.md` or `generate.md`
- Judge prompts collected in `judges.md`
- Phase implementation reads from `prompts/<phase>/...` via Jinja env

## Editing rules

- Changing prompts is a real change. Bump the prompt header version comment, run golden tests.
- Don't sneak SOP changes into a prompt edit — if behaviour changes, update spec/§5 first.
