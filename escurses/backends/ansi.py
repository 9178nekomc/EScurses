"""POSIX（Linux / BSD / macOS）终端后端。

与原版的差别：

* ``termios`` 只在 :meth:`open` 时设置一次 cbreak，``close`` 时还原。
  原版每调一次 ``getch`` 就 ``tcsetattr`` 两次，60fps 下每秒 120 次
  系统调用，还会因为 ``TCSADRAIN`` 丢掉快速连按的键。
* 用 ``os.read`` 直接读裸 fd，避免 Python 文本层的解码缓冲把
  多字节 UTF-8 和方向键序列切碎。
* stdin 不是 TTY（管道、文件、CI）时自动退化成后台线程读，程序不会崩。
"""

from __future__ import annotations

import os
import queue
import shutil
import sys
import threading
from typing import Optional, Tuple

from ..exceptions import TerminalNotSupportedError
from .base import DEFAULT_SIZE, Backend, clamp_size, write_text

try:  # pragma: no cover - Windows 上导入会失败，属预期
    import select
    import termios
    import tty

    _HAS_TERMIOS = True
except ImportError:  # pragma: no cover
    _HAS_TERMIOS = False
    select = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

__all__ = ["AnsiBackend"]

_TERMIOS_ERRORS: Tuple[type, ...] = (OSError,)
if _HAS_TERMIOS:
    _TERMIOS_ERRORS = (OSError, termios.error)  # type: ignore[union-attr]


class AnsiBackend(Backend):
    """基于 termios + ANSI 转义序列的终端后端。"""

    name = "ansi"
    supports_ansi = True

    def __init__(
        self,
        in_fd: Optional[int] = None,
        out=None,
        *,
        raw: bool = False,
    ) -> None:
        self._in_fd = in_fd
        self._out = out if out is not None else sys.stdout
        self._raw = raw
        self._saved_attrs = None
        self._is_tty = False
        self._opened = False
        self._queue: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._stop = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._eof = False

    # ---- 生命周期 ------------------------------------------------------
    @property
    def is_tty(self) -> bool:
        return self._is_tty

    @property
    def is_open(self) -> bool:
        return self._opened

    def open(self) -> None:
        if self._opened:
            return
        if not _HAS_TERMIOS:  # pragma: no cover - 仅 Windows 会走到
            raise TerminalNotSupportedError(
                "当前系统没有 termios，请使用 WindowsBackend"
            )

        fd = self._in_fd
        if fd is None:
            try:
                fd = sys.stdin.fileno()
            except (AttributeError, ValueError, OSError):
                fd = None
        self._in_fd = fd

        if fd is not None:
            try:
                self._is_tty = os.isatty(fd)
            except OSError:  # pragma: no cover
                self._is_tty = False

        if self._is_tty and fd is not None:
            try:
                self._saved_attrs = termios.tcgetattr(fd)
                if self._raw:
                    tty.setraw(fd)
                else:
                    # cbreak：关回显和行缓冲，但保留 ISIG，
                    # 这样 Ctrl-C 依然能触发 KeyboardInterrupt
                    tty.setcbreak(fd)
            except _TERMIOS_ERRORS:  # pragma: no cover
                self._saved_attrs = None
                self._is_tty = False

        if not self._is_tty:
            self._start_reader(fd)

        self._opened = True

    def close(self) -> None:
        if not self._opened:
            return
        self._opened = False
        self._stop.set()
        if self._saved_attrs is not None and self._in_fd is not None:
            try:
                termios.tcsetattr(self._in_fd, termios.TCSADRAIN, self._saved_attrs)  # type: ignore[union-attr]
            except _TERMIOS_ERRORS:  # pragma: no cover
                pass
            self._saved_attrs = None
        reader = self._reader
        if reader is not None and reader.is_alive():
            reader.join(timeout=0.2)
        self._reader = None

    # ---- 输出 ----------------------------------------------------------
    def write(self, text: str) -> None:
        write_text(self._out, text)

    def flush(self) -> None:
        try:
            self._out.flush()
        except (ValueError, OSError):  # pragma: no cover - 流已关闭
            pass

    # ---- 输入 ----------------------------------------------------------
    def read(self, timeout: float = 0.0) -> bytes:
        if self._is_tty and self._in_fd is not None:
            try:
                ready, _w, _x = select.select([self._in_fd], [], [], max(0.0, timeout))
            except (OSError, ValueError):  # pragma: no cover - 终端已断开
                return b""
            if not ready:
                return b""
            try:
                return os.read(self._in_fd, 1024)
            except OSError:  # pragma: no cover
                return b""

        if self._eof:
            return b""
        try:
            item = self._queue.get(timeout=max(0.0, timeout)) if timeout > 0 else self._queue.get_nowait()
        except queue.Empty:
            return b""
        if item is None:
            self._eof = True
            return b""
        return item

    # ---- 尺寸 ----------------------------------------------------------
    def size(self) -> Tuple[int, int]:
        fallback = DEFAULT_SIZE
        try:
            columns, lines = shutil.get_terminal_size(fallback)
        except OSError:  # pragma: no cover
            columns, lines = fallback
        return clamp_size(columns, lines)

    # ---- 内部 ----------------------------------------------------------
    def _start_reader(self, fd: Optional[int]) -> None:
        """stdin 不是 TTY 时用后台线程读，避免阻塞主循环。"""
        stop = self._stop
        queue_ = self._queue

        def pump() -> None:
            try:
                while not stop.is_set():
                    if fd is not None:
                        data = os.read(fd, 1024)
                    else:  # pragma: no cover - fd 都拿不到
                        break
                    if not data:
                        queue_.put(None)
                        return
                    queue_.put(data)
            except (OSError, ValueError):  # pragma: no cover
                queue_.put(None)

        self._reader = threading.Thread(
            target=pump, name="escurses-stdin", daemon=True
        )
        self._reader.start()

    def __repr__(self) -> str:  # pragma: no cover
        return "AnsiBackend(tty=%s, raw=%s)" % (self._is_tty, self._raw)
