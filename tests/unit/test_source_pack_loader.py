from pathlib import Path

import pytest

from llmx_advocate.core.source_pack_loader import (
    InvalidSourcePackError,
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


def test_invalid_yaml_raises():
    text = "---\nfoo: : : :\n---\nbody"
    with pytest.raises(InvalidSourcePackError, match="YAML"):
        parse(text)


def test_missing_required_field_raises():
    text = '---\nschema_version: "1.0"\npack_id: "x"\n---\nbody'
    with pytest.raises(InvalidSourcePackError, match="schema validation"):
        parse(text)
