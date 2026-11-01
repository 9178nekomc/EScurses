"""控件测试。"""

from __future__ import annotations

import pytest

from escurses.screen import Screen
from escurses.widgets import (
    BORDERS,
    center_text,
    draw_box,
    draw_hline,
    draw_paragraph,
    draw_progress_bar,
    draw_sprite,
    draw_text,
    draw_vline,
    pad_text,
    wrap_text,
)


@pytest.fixture
def screen():
    return Screen(10, 6)


class TestDrawText:
    def test_returns_end_column(self, screen):
        assert draw_text(screen, 2, 0, "abc") == 5

    def test_max_width(self, screen):
        assert draw_text(screen, 0, 0, "abcdef", max_width=3) == 3
        assert screen.to_text().split("\n")[0] == "abc       "

    def test_center_text(self, screen):
        start = center_text(screen, 0, "abc")
        assert start == 3
        assert screen.to_text().split("\n")[0] == "   abc    "

    def test_center_text_wide(self, screen):
        start = center_text(screen, 0, "中文")
        assert start == 3  # (10-4)//2


class TestBox:
    def test_single_border(self, screen):
        draw_box(screen, 0, 0, 10, 5)
        lines = screen.to_text().split("\n")
        assert lines[0] == "┌────────┐"
        assert lines[1] == "│        │"
        assert lines[4] == "└────────┘"

    def test_double_border(self, screen):
        draw_box(screen, 0, 0, 6, 3, border="double")
        lines = screen.to_text().split("\n")
        assert lines[0][:6] == "╔════╗"
        assert lines[2][:6] == "╚════╝"

    def test_ascii_border(self, screen):
        draw_box(screen, 0, 0, 4, 3, border="ascii")
        assert screen.to_text().split("\n")[0][:4] == "+--+"

    def test_unknown_border(self, screen):
        with pytest.raises(ValueError) as info:
            draw_box(screen, 0, 0, 5, 3, border="wavy")
        assert "single" in str(info.value)

    @pytest.mark.parametrize("width,height", [(1, 5), (5, 1), (0, 0)])
    def test_too_small_is_noop(self, screen, width, height):
        before = screen.to_text()
        draw_box(screen, 0, 0, width, height)
        assert screen.to_text() == before

    def test_title_is_centred(self, screen):
        draw_box(screen, 0, 0, 10, 5, title="HI")
        assert screen.to_text().split("\n")[0] == "┌───HI───┐"

    def test_title_clipped(self, screen):
        draw_box(screen, 0, 0, 8, 5, title="AAAAAAAAAA")
        line = screen.to_text().split("\n")[0][:8]
        assert line[0] == "┌" and line[-1] == "┐"
        assert "AAAA" in line and "AAAAA" not in line

    def test_box_offscreen(self, screen):
        draw_box(screen, 8, 4, 10, 5)
        # 不应该崩溃，能画的就画
        assert screen.to_text().count("┌") <= 1

    def test_all_border_styles_render(self, screen):
        for name in BORDERS:
            draw_box(screen, 0, 0, 10, 6, border=name)


class TestLines:
    def test_hline(self, screen):
        draw_hline(screen, 0, 0, 4, "-")
        assert screen.to_text().split("\n")[0].startswith("----")

    def test_vline(self, screen):
        draw_vline(screen, 0, 0, 3, "|")
        assert [line[0] for line in screen.to_text().split("\n")[:3]] == ["|"] * 3

    def test_zero_length(self, screen):
        before = screen.to_text()
        draw_hline(screen, 0, 0, 0)
        draw_vline(screen, 0, 0, -1)
        assert screen.to_text() == before


class TestWrapText:
    @pytest.mark.parametrize(
        "text,width,expected",
        [
            ("hello world", 5, ["hello", "world"]),
            ("hello world", 20, ["hello world"]),
            ("中文测试", 4, ["中文", "测试"]),
            ("中文测试", 3, ["中", "文", "测", "试"]),
            ("abcdefgh", 3, ["abc", "def", "gh"]),
            ("a\nb", 10, ["a", "b"]),
            ("", 5, [""]),
            ("aaa bbb", 4, ["aaa", "bbb"]),
        ],
    )
    def test_wrap(self, text, width, expected):
        assert wrap_text(text, width) == expected

    def test_zero_width(self):
        assert wrap_text("abc", 0) == []

    def test_wide_char_not_split(self):
        lines = wrap_text("中中中", 3)
        assert lines == ["中", "中", "中"]

    def test_no_leading_space_on_new_line(self):
        lines = wrap_text("ab cd", 2)
        assert all(not line.startswith(" ") for line in lines)

    def test_every_line_fits(self):
        text = "The quick brown fox jumps over the lazy dog 敏捷的棕色狐狸"
        for width in (5, 8, 13, 20):
            for line in wrap_text(text, width):
                assert len(line) <= width or "\u200d" in line


class TestParagraph:
    def test_returns_line_count(self, screen):
        used = draw_paragraph(screen, 0, 0, 5, "hello world foo")
        assert used == 3

    def test_max_lines(self, screen):
        used = draw_paragraph(screen, 0, 0, 3, "abcdefghi", max_lines=2)
        assert used == 2

    def test_content(self, screen):
        draw_paragraph(screen, 0, 0, 4, "中文测试内容")
        lines = screen.to_text().split("\n")
        assert lines[0] == "中文      "


class TestPadText:
    @pytest.mark.parametrize(
        "text,width,align,expected",
        [
            ("ab", 5, "left", "ab   "),
            ("ab", 5, "right", "   ab"),
            ("ab", 5, "center", " ab  "),
            ("中", 4, "right", "  中"),
            ("中", 4, "center", " 中 "),
            ("abcdef", 3, "left", "abc"),
        ],
    )
    def test_pad(self, text, width, align, expected):
        assert pad_text(text, width, align) == expected


class TestSprite:
    def test_draw(self, screen):
        draw_sprite(screen, 0, 0, ["ab", "cd"])
        lines = screen.to_text().split("\n")
        assert lines[0].startswith("ab")
        assert lines[1].startswith("cd")

    def test_spaces_are_transparent(self, screen):
        screen.fill(0, 0, 10, 2, ".")
        draw_sprite(screen, 0, 0, ["a b"])
        assert screen.to_text().split("\n")[0] == "a.b......."

    def test_wide_chars_keep_alignment(self, screen):
        draw_sprite(screen, 0, 0, ["中x"])
        assert screen.to_text().split("\n")[0].startswith("中x")


class TestProgressBar:
    def test_empty(self, screen):
        draw_progress_bar(screen, 0, 0, 10, 0.0)
        assert screen.to_text().split("\n")[0] == "█░░░░░░░░█"

    def test_full(self, screen):
        draw_progress_bar(screen, 0, 0, 10, 1.0)
        assert screen.to_text().split("\n")[0] == "██████████"

    def test_half(self, screen):
        draw_progress_bar(screen, 0, 0, 10, 0.5)
        assert screen.to_text().split("\n")[0] == "█████░░░░█"

    def test_clamped(self, screen):
        draw_progress_bar(screen, 0, 0, 10, 5.0)
        assert screen.to_text().split("\n")[0] == "██████████"
        draw_progress_bar(screen, 0, 1, 10, -3.0)
        assert screen.to_text().split("\n")[1] == "█░░░░░░░░█"

    def test_nan_is_zero(self, screen):
        draw_progress_bar(screen, 0, 0, 10, float("nan"))
        assert screen.to_text().split("\n")[0] == "█░░░░░░░░█"

    def test_no_bracket(self, screen):
        draw_progress_bar(screen, 0, 0, 4, 0.5, bracket=False)
        assert screen.to_text().split("\n")[0][:4] == "██░░"

    def test_tiny_width(self, screen):
        draw_progress_bar(screen, 0, 0, 1, 0.5)
        draw_progress_bar(screen, 0, 1, 0, 0.5)
        assert True  # 不崩溃即可
