"""显示宽度与文本工具测试。"""

from __future__ import annotations

import pytest

from escurses.textutil import char_width, clusters, sanitize, text_width, truncate


class TestCharWidth:
    @pytest.mark.parametrize(
        "char,expected",
        [
            ("a", 1),
            ("Z", 1),
            ("0", 1),
            ("~", 1),
            ("中", 2),
            ("日", 2),
            ("한", 2),
            ("あ", 2),
            ("Ａ", 2),  # 全角字母
            ("─", 1),  # 制表符是单宽
            ("█", 1),
            ("░", 1),
            ("\u0301", 0),  # 组合重音
            ("\ufe0f", 0),  # 变体选择符
            ("\u200d", 0),  # ZWJ
            ("\x1b", 0),  # 控制字符
            ("\x00", 0),
            ("\t", 0),
        ],
    )
    def test_width(self, char, expected):
        assert char_width(char) == expected

    def test_empty(self):
        assert char_width("") == 0


class TestTextWidth:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("", 0),
            ("hello", 5),
            ("中文", 4),
            ("a中b", 4),
            ("┌─┐", 3),
            ("│x│", 3),
        ],
    )
    def test_width(self, text, expected):
        assert text_width(text) == expected

    def test_combining_mark_adds_nothing(self):
        assert text_width("e\u0301") == 1

    def test_emoji_is_two_columns(self):
        assert text_width("🐍") == 2

    def test_zwj_family_is_one_cluster_of_two_columns(self):
        family = "👨\u200d👩\u200d👧"
        assert text_width(family) == 2
        assert len(clusters(family)) == 1

    def test_vs16_forces_two_columns(self):
        assert text_width("❤\ufe0f") == 2


class TestClusters:
    def test_plain(self):
        assert clusters("ab") == [("a", 1), ("b", 1)]

    def test_mixed_widths(self):
        assert clusters("我ok") == [("我", 2), ("o", 1), ("k", 1)]

    def test_combining_attaches(self):
        result = clusters("e\u0301x")
        assert result[0] == ("e\u0301", 1)
        assert result[1] == ("x", 1)

    def test_empty(self):
        assert clusters("") == []

    def test_leading_zero_width_dropped(self):
        assert clusters("\u0301a") == [("a", 1)]


class TestTruncate:
    @pytest.mark.parametrize(
        "text,width,expected",
        [
            ("hello", 3, "hel"),
            ("hello", 0, ""),
            ("hello", 10, "hello"),
            ("中文", 3, "中"),
            ("中文", 2, "中"),
            ("中文", 4, "中文"),
            ("a中", 1, "a"),
        ],
    )
    def test_truncate(self, text, width, expected):
        assert truncate(text, width) == expected


class TestSanitize:
    def test_escape_is_replaced(self):
        assert sanitize("\x1b[2J") == "?[2J"

    def test_newline_replaced(self):
        assert sanitize("a\nb") == "a?b"

    def test_plain_text_untouched(self):
        assert sanitize("你好 abc") == "你好 abc"

    def test_custom_substitute(self):
        assert sanitize("\x1b", "") == ""

    def test_cjk_untouched(self):
        assert sanitize("中文") == "中文"
