from pathlib import Path

import pytest

from llmx_advocate.core.source_pack_loader import (
    InvalidSourcePackError,
    extract_source_sections,
    parse,
    parse_file,
    split_frontmatter,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "example-pack"


def test_split_frontmatter_basic():
    text = "---\nfoo: bar\n---\n\n# title\n\nbody"
    fm, body = split_frontmatter(text)
    assert "foo: bar" in fm
    assert "# title" in body


def test_missing_frontmatter_raises():
    with pytest.raises(InvalidSourcePackError, match="missing leading"):
        split_frontmatter("# title\nno frontmatter here")


def test_unclosed_frontmatter_raises():
    with pytest.raises(InvalidSourcePackError, match="not closed"):
        split_frontmatter("---\nfoo: bar\nno closing line")


def test_parse_manual_pack_fixture():
    pack = parse_file(FIXTURES / "manual-pack-example.md")
    assert pack.schema_version == "1.0"
    assert pack.created_by == "manual"
    assert pack.source.platform == "manual"
    assert pack.scout_analysis is None  # manual pack omits scout_analysis
    assert "RAG is dead" in pack.body_markdown


def test_parse_scout_pack_fixture():
    pack = parse_file(FIXTURES / "scout-pack-example.md")
    assert pack.scout_analysis is not None
    assert pack.scout_analysis.judgment_seed is not None
    assert pack.scout_analysis.llm_score == 8.5
    assert pack.metrics.hn_score == 423


def test_parse_real_scout_pack_with_full_schema():
    """Real scout-agent v0.1 output — exercises every optional field including
    harvest, language, x_reposts, controversy_signal.url, notes."""
    pack = parse_file(FIXTURES / "scout-real-deepseek-v4.md")
    assert pack.created_by.startswith("llmx-scout-agent")
    assert pack.source.language == "en"
    assert pack.source.platform == "reddit"
    assert pack.scout_analysis is not None
    assert pack.scout_analysis.judgment_seed
    assert pack.scout_analysis.suggested_layer == "留存层"
    assert pack.scout_analysis.controversy_signals
    assert pack.scout_analysis.controversy_signals[0].url is not None
    assert pack.harvest is not None
    assert pack.harvest.fulltext_extracted is True
    assert pack.harvest.fulltext_method == "api"


def test_invalid_yaml_raises():
    text = "---\nfoo: : : :\n---\nbody"
    with pytest.raises(InvalidSourcePackError, match="YAML"):
        parse(text)


def test_missing_required_field_raises():
    text = '---\nschema_version: "1.0"\npack_id: "x"\n---\nbody'
    with pytest.raises(InvalidSourcePackError, match="schema validation"):
        parse(text)


# === extract_source_sections ===
# Per docs/source-pack-schema.md §"Markdown body 段落约定" — these tests pin
# the contract that uniqueness gates only see source sections, never hint
# sections (where scout's judgment_seed lives in human-readable form).


def _scout_body(*, with_seed: bool = True, with_source: bool = True) -> str:
    """Build a scout-style body for tests."""
    parts = ["# 标题\n\n"]
    if with_seed:
        parts.append(
            "## 来源元信息\n\n- 平台: reddit\n\n"
            "## Scout 的预判\n\n判断种子：scout 认为 X 实际上是 Y 的体现。\n\n"
        )
    if with_source:
        parts.append(
            "## 原文正文\n\n这里是原文：作者声称 A 推动了 B。\n\n"
            "## 评论区精华\n\n@user1 (10): 我不同意。@user2 (5): 数据支持作者。\n\n"
            "## 相关讨论\n\n- HN 讨论：另一个角度\n"
        )
    return "".join(parts)


def test_extract_source_sections_strips_hint_segments():
    body = _scout_body(with_seed=True, with_source=True)
    out = extract_source_sections(body)
    # Hint section contents removed
    assert "Scout 的预判" not in out
    assert "判断种子" not in out
    assert "来源元信息" not in out
    # Source section contents preserved
    assert "原文正文" in out
    assert "作者声称 A 推动了 B" in out
    assert "评论区精华" in out
    assert "@user1" in out
    assert "相关讨论" in out


def test_extract_source_sections_keeps_h1_preamble():
    """Content above the first ## heading (typically the H1 title) is kept."""
    body = _scout_body(with_seed=True, with_source=True)
    out = extract_source_sections(body)
    assert "# 标题" in out


def test_extract_source_sections_no_source_returns_full_body():
    """Manual packs without recognised source headings: don't starve the gate."""
    body = "# 手工 pack\n\n这是一个没有 scout 标准小标题的 body。"
    out = extract_source_sections(body)
    assert out == body


def test_extract_source_sections_unknown_section_kept():
    """Authors may add custom ## sections — keep them, don't silently drop."""
    body = (
        "# t\n\n"
        "## Scout 的预判\n\nscout hint\n\n"
        "## 原文正文\n\nreal content\n\n"
        "## 我的笔记\n\ncustom note worth keeping\n"
    )
    out = extract_source_sections(body)
    assert "scout hint" not in out  # hint stripped
    assert "real content" in out  # source kept
    assert "custom note" in out  # unknown section kept


def test_extract_source_sections_empty_body():
    assert extract_source_sections("") == ""
    assert extract_source_sections("   \n  \n").strip() == ""


def test_extract_source_sections_real_trial_pack_seed_isolated():
    """Regression: the 2026-04-28 trial showed P2.5_uniqueness fails when
    scout's judgment_seed bleeds into the body that's fed to the judge.
    After this fix, the seed text must NOT appear in extract_source_sections().
    """
    seed_text = "推理预算分配"
    body = (
        "# The 4B class of 2026 (benchmark)\n\n"
        "## 来源元信息\n\n- 平台: reddit\n\n"
        "## Scout 的预判\n\n"
        f"判断种子：表面是 4B 小模型基准测试排名，但其实揭示了『{seed_text}』比『模型架构』更能决定小模型实际表现。\n\n"
        "## 评论区精华\n\n"
        "@u1 (8): 作者给思考模型只分配 128 token 预算，这是惩罚思考。\n"
    )
    out = extract_source_sections(body)
    assert seed_text not in out, "seed text must not leak into source-only view"
    assert "@u1" in out, "real comment must remain"
