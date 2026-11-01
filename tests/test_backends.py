"""后端测试：平台选择、内存后端、管道输入、编码降级。"""

from __future__ import annotations

import ctypes
import io
import os
import sys
import time

import pytest

from escurses.backends import (
    AnsiBackend,
    MemoryBackend,
    WindowsBackend,
    create_backend,
    current_platform,
)
from escurses.backends.base import clamp_size, write_text
from escurses.backends.windows import _SCANCODE_MAP
from escurses.exceptions import TerminalNotSupportedError
from escurses.input import Key, KeyParser


class TestSelection:
    def test_memory_by_name(self):
        assert isinstance(create_backend("memory"), MemoryBackend)

    def test_instance_passthrough(self):
        backend = MemoryBackend()
        assert create_backend(backend) is backend

    def test_unknown_name(self):
        with pytest.raises(ValueError):
            create_backend("curses")

    def test_platform_name(self):
        assert current_platform() in ("windows", "posix", "unknown")

    @pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows")
    def test_windows_default(self):
        assert isinstance(create_backend(), WindowsBackend)

    @pytest.mark.skipif(sys.platform == "win32", reason="仅 POSIX")
    def test_posix_default(self):
        assert isinstance(create_backend(), AnsiBackend)


class TestClamp:
    def test_clamps_to_range(self):
        assert clamp_size(0, 0) == (1, 1)
        assert clamp_size(99999, 99999) == (1000, 500)

    def test_passes_normal(self):
        assert clamp_size(80, 24) == (80, 24)


class TestMemoryBackend:
    def test_size_forms(self):
        assert MemoryBackend(30, 10).size() == (30, 10)
        assert MemoryBackend((30, 10)).size() == (30, 10)
        assert MemoryBackend(20).size() == (20, 20)

    def test_write_and_take(self):
        backend = MemoryBackend()
        backend.write("abc")
        backend.write("def")
        assert backend.output == "abcdef"
        assert backend.take_output() == "abcdef"
        assert backend.output == ""

    def test_feed_bytes_and_str(self):
        backend = MemoryBackend()
        backend.feed("abc")
        assert backend.read() == b"abc"
        backend.feed(b"\x1b[A")
        assert backend.read() == b"\x1b[A"

    def test_read_empty(self):
        assert MemoryBackend().read() == b""

    def test_feed_rejects_wrong_type(self):
        with pytest.raises(TypeError):
            MemoryBackend().feed(123)

    def test_resize(self):
        backend = MemoryBackend(20, 10)
        backend.set_size(40, 20)
        assert backend.size() == (40, 20)

    def test_tty(self):
        assert MemoryBackend().is_tty is True


class TestAnsiBackend:
    @pytest.mark.skipif(sys.platform == "win32", reason="需要 termios")
    def test_pipe_input(self):
        read_fd, write_fd = os.pipe()
        backend = AnsiBackend(in_fd=read_fd, out=io.StringIO())
        try:
            backend.open()
            assert backend.is_tty is False
            os.write(write_fd, b"hi")
            data = b""
            deadline = time.time() + 2.0
            while not data and time.time() < deadline:
                data = backend.read(0.05)
            assert data == b"hi"
        finally:
            backend.close()
            os.close(read_fd)
            os.close(write_fd)

    def test_close_is_idempotent(self):
        backend = AnsiBackend(in_fd=None, out=io.StringIO())
        backend.close()
        backend.close()

    def test_write_goes_to_stream(self):
        stream = io.StringIO()
        backend = AnsiBackend(out=stream)
        backend.write("x")
        backend.flush()
        assert stream.getvalue() == "x"

    def test_size_is_sane(self):
        backend = AnsiBackend(out=io.StringIO())
        width, height = backend.size()
        assert 1 <= width <= 1000
        assert 1 <= height <= 500


class TestWindowsBackend:
    @pytest.mark.skipif(sys.platform == "win32", reason="Windows 上可以真的打开")
    def test_unavailable_off_windows(self):
        with pytest.raises(TerminalNotSupportedError):
            WindowsBackend().open()

    def test_close_without_open(self):
        WindowsBackend().close()

    @pytest.mark.parametrize(
        "code,expected",
        [
            ("H", Key.UP),
            ("P", Key.DOWN),
            ("M", Key.RIGHT),
            ("K", Key.LEFT),
            ("G", Key.HOME),
            ("O", Key.END),
            ("R", Key.INSERT),
            ("S", Key.DELETE),
            ("I", Key.PAGE_UP),
            ("Q", Key.PAGE_DOWN),
            (";", Key.F1),
            ("<", Key.F2),
            ("=", Key.F3),
            (">", Key.F4),
            ("?", Key.F5),
            ("@", Key.F6),
            ("A", Key.F7),
            ("B", Key.F8),
            ("C", Key.F9),
            ("D", Key.F10),
            ("\x85", Key.F11),
            ("\x86", Key.F12),
        ],
    )
    def test_scancodes_round_trip_through_parser(self, code, expected):
        """Windows 扫描码翻译成的序列，必须被统一解析器还原成同一个键。"""
        data = _SCANCODE_MAP[code]
        events = KeyParser().feed(data)
        assert len(events) == 1
        assert events[0].key is expected

    @pytest.mark.parametrize("code", ["\x73", "\x74", "\x8d", "\x91"])
    def test_ctrl_arrow_scancodes(self, code):
        events = KeyParser().feed(_SCANCODE_MAP[code])
        assert len(events) == 1
        assert "CTRL" in str(events[0].modifiers)


class TestWriteText:
    def test_normal(self):
        stream = io.StringIO()
        write_text(stream, "abc")
        assert stream.getvalue() == "abc"

    def test_empty_is_noop(self):
        stream = io.StringIO()
        write_text(stream, "")
        assert stream.getvalue() == ""

    def test_encoding_failure_falls_back(self):
        class AsciiOnly(io.TextIOBase):
            encoding = "ascii"

            def __init__(self):
                self.buffer = io.BytesIO()
                self.chunks = []

            def write(self, text):
                text.encode("ascii")  # 会抛 UnicodeEncodeError
                self.chunks.append(text)
                return len(text)

            def flush(self):
                pass

        stream = AsciiOnly()
        write_text(stream, "中")
        assert stream.buffer.getvalue() == b"?"


class TestWindowsStructs:
    def test_console_screen_buffer_info_layout(self):
        """结构体布局必须和 Win32 头文件一致，否则读出来的是垃圾。"""
        from escurses.backends.windows import _CONSOLE_SCREEN_BUFFER_INFO

        # COORD(4) + COORD(4) + WORD(2) + SMALL_RECT(8) + COORD(4) = 22
        assert ctypes.sizeof(_CONSOLE_SCREEN_BUFFER_INFO) == 22

    def test_std_handle_is_64bit_safe(self):
        """GetStdHandle 的返回值不能按 32 位 int 解析。"""
        from escurses.backends import windows as mod

        if mod._kernel32 is None:  # pragma: no cover - 非 Windows
            pytest.skip("非 Windows 平台")
        assert mod._get_std_handle(mod._STD_OUTPUT_HANDLE) is not None

    def test_console_mode_of_invalid_handle_is_none(self):
        from escurses.backends import windows as mod

        if mod._kernel32 is None:  # pragma: no cover
            pytest.skip("非 Windows 平台")
        assert mod._console_mode(0) is None
