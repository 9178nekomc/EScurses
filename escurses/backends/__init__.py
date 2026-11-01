"""后端自动选择。"""

from __future__ import annotations

import os
import sys
from typing import Optional

from ..exceptions import TerminalNotSupportedError
from .ansi import AnsiBackend
from .base import Backend
from .memory import MemoryBackend
from .windows import WindowsBackend

__all__ = [
    "Backend",
    "AnsiBackend",
    "WindowsBackend",
    "MemoryBackend",
    "create_backend",
    "current_platform",
]


def current_platform() -> str:
    """返回 ``"windows"`` / ``"posix"`` / ``"unknown"``。"""
    if sys.platform == "win32":
        return "windows"
    if os.name == "posix":
        return "posix"
    return "unknown"


def create_backend(prefer: Optional[object] = None, out=None) -> Backend:
    """按当前平台创建后端。

    :param prefer: 显式指定后端实例；传字符串 ``"memory"``/``"ansi"``/``"windows"``
        则按名字创建。
    :raises TerminalNotSupportedError: 平台无法提供可用后端
    """
    if prefer is not None:
        if isinstance(prefer, str):
            name = prefer.strip().lower()
            if name == "memory":
                return MemoryBackend()
            if name == "ansi":
                return AnsiBackend(out=out)
            if name == "windows":
                return WindowsBackend(out=out)
            raise ValueError("未知后端名：%r" % (prefer,))
        return prefer  # 鸭子类型，不做 isinstance 检查

    platform = current_platform()
    if platform == "windows":
        return WindowsBackend(out=out)
    if platform == "posix":
        return AnsiBackend(out=out)
    raise TerminalNotSupportedError(
        "无法识别当前平台（os.name=%r），请手动传入 backend" % (os.name,)
    )
