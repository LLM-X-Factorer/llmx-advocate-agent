from llmx_advocate.core.qa.rules import (
    RELAY_PHRASES,
    SOURCE_BACKING_BLACKLIST,
    char_count_chinese,
    contains_any,
    expected_duration,
)


def test_blacklist_hit():
    text = "今天聊一个 HN 热榜的文章"
    assert contains_any(text, SOURCE_BACKING_BLACKLIST) is not None


def test_relay_phrase_hit():
    text = "我来给大家解读一下"
    assert contains_any(text, RELAY_PHRASES) is not None


def test_clean_text_passes():
    text = "很多人以为豆包手机被封杀是因为安全问题，但真正的原因是它动了巨头的命根子"
    assert contains_any(text, SOURCE_BACKING_BLACKLIST) is None
    assert contains_any(text, RELAY_PHRASES) is None


def test_duration_formula():
    text = "x" * 32
    assert expected_duration(text) == max(5.0, 32 / 3.2 + 2.0)


def test_char_count_excludes_whitespace():
    assert char_count_chinese("hello world") == 10
