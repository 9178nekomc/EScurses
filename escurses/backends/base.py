"""终端后端接口。

把"跟操作系统打交道"的部分全部收敛到这里，上层（缓冲区、渲染、控件）
就变成了纯逻辑，可以脱离真实终端做单元测试。

一个后端只负责四件事：

* 打开 / 关闭终端（切换模式、保存与恢复状态）；
* :meth:`Backend.write` —— 把字符串写给终端；
* :meth:`Backend.read`  —— 拿到原始字节（没有输入就返回空 bytes）；
* :meth:`Backend.size`  —— 报告可见区域尺寸。
"""

from __future__ import annotations

from typing import Tuple

__all__ = ["Backend", "clamp_size"]

#: 尺寸上下限。下限防止 0 尺寸导致除零，上限防止某些终端（尤其是
#: Windows 控制台）报告出 300x9001 的缓冲区尺寸，直接把内存吃光。
MIN_WIDTH, MIN_HEIGHT = 1, 1
MAX_WIDTH, MAX_HEIGHT = 1000, 500
DEFAULT_SIZE = (80, 24)


def clamp_size(width: int, height: int) -> Tuple[int, int]:
    """把终端报告的尺寸夹到安全范围内。"""
    width = max(MIN_WIDTH, min(MAX_WIDTH, int(width)))
    height = max(MIN_HEIGHT, min(MAX_HEIGHT, int(height)))
    return (width, height)


class Backend:
    """后端的鸭子类型接口。

    不强制继承 —— 只要实现了这些方法就能传给 :class:`escurses.Terminal`，
    写测试替身时不必依赖本模块。
    """

    #: 后端名字，出现在错误信息里
    name = "abstract"

    #: 是否支持 ANSI 转义序列
    supports_ansi = True

    @property
    def is_tty(self) -> bool:
        """当前是否真的有可交互终端。"""
        raise NotImplementedError

    def open(self) -> None:
        """进入游戏模式（保存终端状态、切换模式）。"""

    def close(self) -> None:
        """恢复终端状态。必须可重复调用。"""

    def write(self, text: str) -> None:
        """输出字符串。"""
        raise NotImplementedError

    def flush(self) -> None:
        """刷新输出缓冲。"""

    def read(self, timeout: float = 0.0) -> bytes:
        """读取原始字节；``timeout=0`` 时为非阻塞。没有数据返回 ``b""``。"""
        raise NotImplementedError

    def size(self) -> Tuple[int, int]:
        """返回 ``(列, 行)``。"""
        raise NotImplementedError


def write_text(stream, text: str) -> None:
    """向文本流写字符串，遇到编码不支持时降级而不是崩溃。

    典型场景：Windows 控制台在 CP936 代码页下输出 emoji，``write`` 会抛
    :class:`UnicodeEncodeError`。这里改用带 ``replace`` 的编码重写一遍，
    最坏情况是几个问号，而不是整个游戏崩掉。
    """
    if not text:
        return
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        buffer = getattr(stream, "buffer", None)
        safe = text.encode(encoding, "replace")
        if buffer is not None:
            try:
                stream.flush()
            except (ValueError, OSError):  # pragma: no cover
                pass
            buffer.write(safe)
        else:  # pragma: no cover
            stream.write(safe.decode(encoding, "replace"))
