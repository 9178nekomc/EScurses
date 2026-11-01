"""Windows 控制台后端。

原版只在 Windows 上调了个 ``msvcrt.getwch()``，有三个硬伤：

1. 没有开启 ``ENABLE_VIRTUAL_TERMINAL_PROCESSING``。Windows 10 的 conhost
   默认不解析 ANSI 转义序列，于是 ``\\x1b[2J`` 会以字面量 ``←[2J`` 打在屏幕上。
2. 方向键返回两个字符（``\\x00``/``\\xe0`` 前缀 + 扫描码），原版把前缀直接
   当成按键返回，方向键永远只能收到半个事件。
3. 没处理 UTF-16 代理对，emoji 会被拆成两个乱码。

这里把扫描码翻译成标准的 ANSI 序列交给统一的 :class:`escurses.input.KeyParser`
处理，两个平台共用同一套按键语义。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import shutil
import sys
import threading
import time
from typing import Optional, Tuple

from ..exceptions import TerminalNotSupportedError
from .base import DEFAULT_SIZE, Backend, clamp_size, write_text

try:  # pragma: no cover - 非 Windows 平台
    import msvcrt

    _HAS_MSVCRT = True
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore[assignment]
    _HAS_MSVCRT = False

__all__ = ["WindowsBackend"]

ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
ENABLE_PROCESSED_OUTPUT = 0x0001

#: ``\x00`` / ``\xe0`` 前缀之后的扫描码 → 标准 ANSI 序列
_SCANCODE_MAP = {
    "H": b"\x1b[A",       # Up
    "P": b"\x1b[B",       # Down
    "M": b"\x1b[C",       # Right
    "K": b"\x1b[D",       # Left
    "G": b"\x1b[H",       # Home
    "O": b"\x1b[F",       # End
    "R": b"\x1b[2~",      # Insert
    "S": b"\x1b[3~",      # Delete
    "I": b"\x1b[5~",      # PageUp
    "Q": b"\x1b[6~",      # PageDown
    ";": b"\x1bOP",       # F1
    "<": b"\x1bOQ",       # F2
    "=": b"\x1bOR",       # F3
    ">": b"\x1bOS",       # F4
    "?": b"\x1b[15~",     # F5
    "@": b"\x1b[17~",     # F6
    "A": b"\x1b[18~",     # F7
    "B": b"\x1b[19~",     # F8
    "C": b"\x1b[20~",     # F9
    "D": b"\x1b[21~",     # F10
    "\x85": b"\x1b[23~",  # F11
    "\x86": b"\x1b[24~",  # F12
    "\x73": b"\x1b[1;5D",  # Ctrl+Left
    "\x74": b"\x1b[1;5C",  # Ctrl+Right
    "\x8d": b"\x1b[1;5A",  # Ctrl+Up
    "\x91": b"\x1b[1;5B",  # Ctrl+Down
}

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None


class _COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", wintypes.SHORT),
        ("Top", wintypes.SHORT),
        ("Right", wintypes.SHORT),
        ("Bottom", wintypes.SHORT),
    ]


class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    """``ctypes.wintypes`` 里没有这个结构体，得自己声明。"""

    _fields_ = [
        ("dwSize", _COORD),
        ("dwCursorPosition", _COORD),
        ("wAttributes", wintypes.WORD),
        ("srWindow", _SMALL_RECT),
        ("dwMaximumWindowSize", _COORD),
    ]


# WHY: 必须显式声明 restype/argtypes。ctypes 默认把所有返回值当成 C int（32 位），
# 而 HANDLE 在 64 位 Windows 上是 64 位指针 —— 不声明就会被静默截断，
# GetConsoleMode / GetConsoleScreenBufferInfo 一律失败（返回 0），
# 表现为"终端明明在那儿却报不支持"。
if _kernel32 is not None:  # pragma: no cover - 仅在 Windows 上执行
    _kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    _kernel32.GetStdHandle.restype = wintypes.HANDLE

    _kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.GetConsoleMode.restype = wintypes.BOOL

    _kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.SetConsoleMode.restype = wintypes.BOOL

    _kernel32.GetConsoleScreenBufferInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFO),
    ]
    _kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL

#: GetStdHandle 的参数是无符号 DWORD，-11 要按位转成 0xFFFFFFF5 传进去
_STD_OUTPUT_HANDLE = 0xFFFFFFF5
_STD_INPUT_HANDLE = 0xFFFFFFF6


def _get_std_handle(which: int):
    if _kernel32 is None:  # pragma: no cover
        return None
    return _kernel32.GetStdHandle(which & 0xFFFFFFFF)


def _console_mode(handle) -> Optional[int]:
    if _kernel32 is None or handle is None:  # pragma: no cover
        return None
    mode = wintypes.DWORD()
    if not _kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return None
    return int(mode.value)


def _set_console_mode(handle, mode: int) -> bool:
    if _kernel32 is None or handle is None:  # pragma: no cover
        return False
    return bool(_kernel32.SetConsoleMode(handle, mode))


def console_window_size() -> Optional[Tuple[int, int]]:
    """返回控制台**可见窗口**尺寸。

    不能用 ``os.get_terminal_size()``：Windows 下某些配置会返回屏幕缓冲区
    尺寸（常见 9001 行），照它分配单元格等于直接吃掉几百 MB 内存。
    """
    if sys.platform != "win32" or _kernel32 is None:  # pragma: no cover
        return None
    handle = _get_std_handle(_STD_OUTPUT_HANDLE)
    info = _CONSOLE_SCREEN_BUFFER_INFO()
    if not _kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
        return None
    width = info.srWindow.Right - info.srWindow.Left + 1
    height = info.srWindow.Bottom - info.srWindow.Top + 1
    if width <= 0 or height <= 0:  # pragma: no cover
        return None
    return (int(width), int(height))


class WindowsBackend(Backend):
    """Windows 控制台后端。"""

    name = "windows"
    supports_ansi = True

    def __init__(self, out=None, *, raw: bool = True) -> None:
        self._out = out if out is not None else sys.stdout
        self._old_mode: Optional[int] = None
        self._opened = False
        self._console = False
        self._queue = None  # type: Optional["threading.Thread"]
        self._buffer = bytearray()
        self._pending_high = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._eof = False

    # ---- 生命周期 ------------------------------------------------------
    @property
    def is_tty(self) -> bool:
        return self._console

    @property
    def is_open(self) -> bool:
        return self._opened

    def open(self) -> None:
        if self._opened:
            return
        if not _HAS_MSVCRT or _kernel32 is None:  # pragma: no cover
            raise TerminalNotSupportedError("当前不是 Windows 环境")

        out_is_tty = _is_stream_tty(self._out)
        if out_is_tty:
            handle = _get_std_handle(_STD_OUTPUT_HANDLE)
            current = _console_mode(handle)
            if current is None:
                if console_window_size() is None:
                    # isatty() 说"是终端"，但两种查询都失败 —— 这个句柄其实
                    # 不是控制台（Git Bash 把 >/dev/null 映射成字符设备就是
                    # 这种情况）。此时既不用开 VT，也不必报错。
                    out_is_tty = False
                else:
                    raise TerminalNotSupportedError("无法获取控制台模式")
            else:
                self._old_mode = current
                desired = (
                    current
                    | ENABLE_PROCESSED_OUTPUT
                    | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                )
                if not _set_console_mode(handle, desired):
                    # 老系统（Win7/8/早期 Win10）不支持 VT，别装作能用
                    self._old_mode = None
                    raise TerminalNotSupportedError(
                        "当前控制台不支持 ANSI 转义序列（需要 Windows 10 1511+）"
                    )

        self._console = _is_stream_tty(sys.stdin)
        if not self._console:
            self._start_reader()
        self._opened = True

    def close(self) -> None:
        if not self._opened:
            return
        self._opened = False
        self._stop.set()
        if self._old_mode is not None:
            try:
                _set_console_mode(_get_std_handle(_STD_OUTPUT_HANDLE), self._old_mode)
            except (OSError, ValueError):  # pragma: no cover
                pass
            self._old_mode = None
        thread = self._queue
        if isinstance(thread, threading.Thread) and thread.is_alive():
            thread.join(timeout=0.2)
        self._queue = None

    # ---- 输出 ----------------------------------------------------------
    def write(self, text: str) -> None:
        write_text(self._out, text)

    def flush(self) -> None:
        try:
            self._out.flush()
        except (ValueError, OSError):  # pragma: no cover
            pass

    # ---- 输入 ----------------------------------------------------------
    def read(self, timeout: float = 0.0) -> bytes:
        if not self._console:
            return self._read_pipe(timeout)

        deadline = time.monotonic() + max(0.0, timeout)
        collected = bytearray()
        while True:
            chunk = self._read_console_key()
            if chunk:
                collected.extend(chunk)
                if timeout <= 0:
                    break
            if time.monotonic() >= deadline:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.005, remaining))
        return bytes(collected)

    def _read_pipe(self, timeout: float) -> bytes:
        with self._lock:
            if self._buffer:
                data = bytes(self._buffer)
                self._buffer.clear()
                return data
        if self._eof:
            return b""
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            with self._lock:
                if self._buffer:
                    data = bytes(self._buffer)
                    self._buffer.clear()
                    return data
            if time.monotonic() >= deadline:
                return b""
            time.sleep(0.002)

    def _read_console_key(self) -> bytes:
        """非阻塞读一个按键，翻译成 ANSI 字节序列。"""
        if not msvcrt.kbhit():  # type: ignore[union-attr]
            return b""
        char = msvcrt.getwch()  # type: ignore[union-attr]

        if char in ("\x00", "\xe0"):
            if not msvcrt.kbhit():  # type: ignore[union-attr]
                return b""  # 前缀到了但扫描码没到，直接丢弃，避免错位
            code = msvcrt.getwch()  # type: ignore[union-attr]
            return _SCANCODE_MAP.get(code, b"")

        if "\ud800" <= char <= "\udbff":
            # 高位代理，等下一个低位代理凑成完整码位
            self._pending_high = char
            return b""
        if "\udc00" <= char <= "\udfff":
            if not self._pending_high:
                return b""
            high = self._pending_high
            self._pending_high = ""
            codepoint = 0x10000 + ((ord(high) - 0xD800) << 10) + (ord(char) - 0xDC00)
            return chr(codepoint).encode("utf-8")
        return char.encode("utf-8")

    # ---- 尺寸 ----------------------------------------------------------
    def size(self) -> Tuple[int, int]:
        reported = console_window_size()
        if reported is None:
            try:
                columns, lines = shutil.get_terminal_size(DEFAULT_SIZE)
            except OSError:  # pragma: no cover
                columns, lines = DEFAULT_SIZE
            reported = (columns, lines)
        return clamp_size(*reported)

    # ---- 内部 ----------------------------------------------------------
    def _start_reader(self) -> None:
        """stdin 不是控制台时用后台线程读。

        必须走裸 fd 的 ``os.read``，不能用 ``sys.stdin.buffer.read``：
        后者会持有 :class:`io.BufferedReader` 的锁，而线程会一直阻塞在
        ``read`` 上直到有输入。解释器退出时会因为抢不到这把锁直接
        ``Fatal Python error: _enter_buffered_busy`` 崩掉（退出码 139）。
        ``os.read`` 不碰 Python 层的锁，进程可以干净退出。
        """
        try:
            fd = sys.stdin.fileno()
        except (AttributeError, ValueError, OSError):  # pragma: no cover
            return

        stop = self._stop
        buffer = self._buffer
        lock = self._lock
        backend = self

        def pump() -> None:
            try:
                while not stop.is_set():
                    data = os.read(fd, 1024)
                    if not data:
                        backend._eof = True
                        return
                    with lock:
                        buffer.extend(data)
            except (OSError, ValueError):
                backend._eof = True

        thread = threading.Thread(target=pump, name="escurses-stdin", daemon=True)
        self._queue = thread
        thread.start()

    def __repr__(self) -> str:  # pragma: no cover
        return "WindowsBackend(console=%s)" % (self._console,)


def _is_stream_tty(stream) -> bool:
    isatty = getattr(stream, "isatty", None)
    try:
        return bool(callable(isatty) and isatty())
    except (ValueError, OSError):  # pragma: no cover
        return False
