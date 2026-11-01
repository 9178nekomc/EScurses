"""渲染器测试：验证增量输出确实是"最小且正确"的。"""

from __future__ import annotations

import pytest

from escurses import Style, set_color_support
from escurses.render import render, render_full
from escurses.screen import Screen
from vt import VirtualTerminal


def snapshot(screen):
    return [screen.row(y) for y in range(screen.height)]


@pytest.fixture(autouse=True)
def truecolor():
    """渲染测试要断言颜色序列，先把色彩能力固定住。"""
    set_color_support("truecolor")
    yield
    set_color_support(None)


@pytest.fixture
def screen():
    return Screen(6, 2)


class TestFullRender:
    def test_first_frame(self, screen):
        screen.put(0, 0, "abc")
        out = render(None, screen)
        assert out.startswith("\x1b[1;1H")
        assert "abc" in out

    def test_all_rows_present(self, screen):
        out = render(None, screen)
        assert "\x1b[1;1H" in out
        assert "\x1b[2;1H" in out

    def test_render_full_helper(self, screen):
        assert render_full(screen) == render(None, screen)


class TestIncremental:
    def test_no_change_produces_nothing(self, screen):
        front = snapshot(screen)
        screen.clear_dirty()
        assert render(front, screen) == ""

    def test_only_dirty_row(self, screen):
        front = snapshot(screen)
        screen.clear_dirty()
        screen.put(1, 1, "x")
        out = render(front, screen)
        assert out == "\x1b[2;2Hx"
        assert "\x1b[1;" not in out

    def test_minimal_span(self, screen):
        front = snapshot(screen)
        screen.clear_dirty()
        screen.put(2, 0, "x")
        # 只定位到 (第 1 行, 第 3 列)，不重画整行
        assert render(front, screen) == "\x1b[1;3Hx"

    def test_changed_cell_erases_old(self, screen):
        screen.put(0, 0, "abc")
        front = snapshot(screen)
        screen.clear_dirty()
        screen.put(0, 0, "  ")
        out = render(front, screen)
        assert out == "\x1b[1;1H  "


class TestStyles:
    def test_style_switch(self, screen):
        screen.put(0, 0, "a")
        screen.put(1, 0, "b", Style(bold=True))
        out = render(None, screen)
        assert "\x1b[0;1m" in out

    def test_red_is_emitted(self, screen):
        screen.put(0, 0, "a", Style(fg="red"))
        out = render(None, screen)
        # 命名色走 16 色调色板，交给终端解释，不会锁死成具体 RGB
        assert "\x1b[0;31m" in out

    def test_truecolor_is_emitted(self, screen):
        screen.put(0, 0, "a", Style(fg="#ff8800"))
        out = render(None, screen)
        assert "\x1b[0;38;2;255;136;0m" in out

    def test_frame_leaves_terminal_in_default_attrs(self, screen):
        """一帧结束后终端必须回到默认样式，否则下一帧的空白也会带颜色。"""
        screen.put(0, 0, "a", Style(fg="red", bold=True))
        screen.put(3, 0, "b", Style(fg="blue"))
        vt = VirtualTerminal(6, 2)
        vt.feed(render(None, screen))
        assert vt.attr == "0"

    def test_default_style_no_reset_when_never_styled(self, screen):
        screen.put(0, 0, "a")
        out = render(None, screen)
        assert "\x1b[0m" not in out


class TestWideChars:
    def test_wide_char_emitted_once(self, screen):
        front = snapshot(screen)
        screen.clear_dirty()
        screen.put(1, 0, "中")
        out = render(front, screen)
        assert out == "\x1b[1;2H中"

    def test_start_snaps_back_to_wide_char(self):
        """如果差异起点落在宽字符的后半截，必须回退到前半截。"""
        screen = Screen(6, 1)
        screen.put(1, 0, "中")
        screen.clear_dirty()
        front = snapshot(screen)
        # 人为制造"只差后半截"的不一致状态
        front[0][2] = ("x", "0")
        screen.mark_dirty(0)
        out = render(front, screen)
        assert out.startswith("\x1b[1;2H")
        assert "中" in out


class TestConsistency:
    @pytest.mark.parametrize("full", [True, False])
    def test_row_count_never_exceeds_screen(self, screen, full):
        screen.put(0, 0, "abcdef")
        screen.put(0, 1, "中文")
        out = render(None if full else snapshot(screen), screen)
        for chunk in out.split("\x1b[")[1:]:
            if chunk[:-1].replace(";", "").isdigit():
                row = int(chunk.split(";")[0])
                assert 1 <= row <= screen.height
