"""EScurses 异常类型。

全部继承 :class:`RuntimeError`，这样只写 ``except Exception`` 的老代码
仍然能接住它们，不会因为升级库而崩溃。
"""

from __future__ import annotations

__all__ = [
    "EscursesError",
    "TerminalNotSupportedError",
    "TerminalStateError",
    "ScreenBoundsError",
]


class EscursesError(RuntimeError):
    """所有 EScurses 异常的基类。"""


class TerminalNotSupportedError(EscursesError):
    """当前环境无法提供可用的终端后端。

    常见原因：stdout 被重定向到文件、运行在无 TTY 的容器里、
    或者使用了未知的 ``os.name``。
    """


class TerminalStateError(EscursesError):
    """在没有初始化、或已经关闭的终端上执行了操作。

    典型场景：还没调用 ``initGame()`` 就调用 ``refresh()``。
    """


class ScreenBoundsError(EscursesError, IndexError):
    """坐标超出缓冲区范围。

    同时继承 :class:`IndexError`：旧版本越界时抛的就是 IndexError，
    这样老代码里的 ``except IndexError`` 依然有效。
    """
