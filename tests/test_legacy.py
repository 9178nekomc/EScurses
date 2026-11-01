"""旧版函数式 API 兼容性测试。

这些函数是"已经用它写了游戏的孩子们"的合同，改动必须是纯增益。
"""

from __future__ import annotations

import pytest

import escurses
from escurses import MemoryBackend
from escurses.exceptions import TerminalStateError


@pytest.fixture
def api():
    backend = MemoryBackend(20, 6)
    escurses.initGame(backend=backend)
    return backend


class TestInit:
    def test_creates_screen(self, api):
        assert escurses._screen is not None
        assert escurses._screenWidth == 20
        assert escurses._screenHeight == 6

    def test_returns_screen(self, api):
        screen = escurses.initGame()
        assert screen is escurses.getScreen()

    def test_idempotent(self, api):
        escurses.drawChar(1, 1, "X")
        escurses.initGame()  # 旧版会在这里把画好的东西清掉
        assert escurses._screen.char_at(0, 0) == "X"

    def test_screen_attribute_forwarded(self, api):
        # 模块级 __getattr__ 必须动态转发，否则 _screen 会失去同步
        assert escurses._screen is escurses.getScreen()


class TestDrawChar:
    def test_one_based_coordinates(self, api):
        escurses.drawChar(1, 1, "@")
        assert escurses._screen.char_at(0, 0) == "@"

    def test_second_row(self, api):
        escurses.drawChar(3, 2, "#")
        assert escurses._screen.char_at(2, 1) == "#"

    def test_last_column_works(self, api):
        """旧版缓冲区少一列，画最右边一列直接 IndexError。"""
        escurses.drawChar(20, 1, "x")
        assert escurses._screen.char_at(19, 0) == "x"

    def test_no_index_error_out_of_bounds(self, api):
        escurses.drawChar(999, 999, "x")  # 不该抛异常

    def test_type_errors(self, api):
        with pytest.raises(TypeError):
            escurses.drawChar("1", 1, "x")
        with pytest.raises(TypeError):
            escurses.drawChar(1, 1, 5)

    def test_empty_string_ignored(self, api):
        escurses.drawChar(1, 1, "")
        assert escurses._screen.char_at(0, 0) == " "


class TestRefresh:
    def test_writes_output(self, api):
        escurses.drawChar(1, 1, "A")
        escurses.refresh()
        assert "A" in api.output

    def test_without_init_raises(self):
        escurses.shutdown()
        with pytest.raises(TerminalStateError):
            escurses.refresh()


class TestClear:
    def test_clears_buffer(self, api):
        escurses.drawChar(1, 1, "A")
        escurses.clear()
        assert escurses._screen.char_at(0, 0) == " "

    def test_emits_home(self, api):
        api.take_output()
        escurses.clear()
        assert "\x1b[2J" in api.output
        assert "\x1b[H" in api.output


class TestGetch:
    def test_returns_char(self, api):
        api.feed(b"a")
        assert escurses.getch() == "a"

    def test_returns_none_when_empty(self, api):
        assert escurses.getch() is None

    def test_arrow_returns_name(self, api):
        api.feed(b"\x1b[A")
        assert escurses.getch() == escurses.KEY_UP

    def test_arrow_constants_are_strings(self, api):
        api.feed(b"\x1b[B")
        assert escurses.getch() == "DOWN"

    def test_enter_and_tab(self, api):
        api.feed(b"\r")
        assert escurses.getch() == "\r"
        api.feed(b"\t")
        assert escurses.getch() == "\t"

    def test_getkey_returns_event(self, api):
        api.feed(b"\x1b[1;5C")
        event = escurses.getkey()
        assert event.key is escurses.Key.RIGHT

    def test_getch_before_init_does_not_crash(self):
        escurses.shutdown()
        # 没有 initGame 时 getch 仍然可用（旧版也支持）
        assert escurses.getch() is None


class TestCursorEcho:
    def test_hide(self, api):
        escurses.cursorEcho()
        assert "\x1b[?25l" in api.output

    def test_show(self, api):
        escurses.cursorEcho(True)
        assert "\x1b[?25h" in api.output

    def test_works_without_init(self, capsys):
        escurses.shutdown()
        escurses.cursorEcho(True)  # 直接写 stdout，不崩
        assert capsys.readouterr().out == "\x1b[?25h"


class TestExitGame:
    def test_raises_system_exit(self, api):
        with pytest.raises(SystemExit) as info:
            escurses.exitGame()
        assert info.value.code == 0

    def test_restores_terminal(self, api):
        with pytest.raises(SystemExit):
            escurses.exitGame()
        assert "\x1b[?1049l" in api.output

    def test_no_subprocess_used(self, api, monkeypatch):
        """旧版用 subprocess.run("cls") 清屏，这里必须完全不用子进程。"""
        import subprocess

        def boom(*args, **kwargs):
            raise AssertionError("不应该再调用 subprocess")

        monkeypatch.setattr(subprocess, "run", boom)
        with pytest.raises(SystemExit):
            escurses.exitGame()


class TestTiming:
    def test_frame_helpers_do_not_crash(self):
        escurses.frameStart()
        elapsed = escurses.sleepForFrame(1000)
        assert elapsed >= 0

    def test_high_fps_not_clamped_to_100(self):
        """旧版自旋条件写死 10ms，fps > 100 时会被强行拖慢。"""
        escurses.frameStart()
        elapsed = escurses.sleepForFrame(500)  # 2ms 一帧
        assert elapsed == pytest.approx(0.002, abs=0.004)


class TestEnvironment:
    def test_get_terminal_size(self):
        size = escurses.getTerminalSize()
        assert len(size) == 2
        assert size[0] > 0 and size[1] > 0

    def test_terminal_check_returns_bool(self):
        assert isinstance(escurses.linuxTerminalCheck(), bool)

    def test_shutdown_is_idempotent(self):
        escurses.shutdown()
        escurses.shutdown()
