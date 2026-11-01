"""内存后端：不碰真实终端，把输出收集到内存、从队列取输入。

用途：

* 单元测试与 CI（没有 TTY 也能跑完整渲染）；
* 录屏 / 回放：把一局游戏的全部输出字节存下来再喂给虚拟终端；
* 作为"降级后端"，当环境完全没有终端时仍然让程序跑完不崩。
"""

from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional, Tuple

from .base import DEFAULT_SIZE, Backend, clamp_size

__all__ = ["MemoryBackend"]


class MemoryBackend(Backend):
    """把终端抽象成内存对象。

    :param size: 初始 ``(列, 行)``
    :param echo_stdout: 是否同时把输出透传到真实 stdout（调试用）
    """

    name = "memory"
    supports_ansi = True

    def __init__(
        self,
        size: object = DEFAULT_SIZE,
        height: Optional[int] = None,
        *,
        echo_stdout: bool = False,
    ) -> None:
        if height is not None:
            size = (int(size), int(height))  # type: ignore[arg-type]
        if isinstance(size, int):
            size = (size, size)
        self._size = clamp_size(*size)  # type: ignore[misc]
        self._chunks: List[str] = []
        self._input: Deque[bytes] = deque()
        self._pending = bytearray()
        self._open = False
        self._echo_stdout = echo_stdout
        self.writes = 0

    # ---- 生命周期 ------------------------------------------------------
    @property
    def is_tty(self) -> bool:
        return True

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    # ---- 输出 ----------------------------------------------------------
    def write(self, text: str) -> None:
        if not text:
            return
        self._chunks.append(text)
        self.writes += 1
        if self._echo_stdout:  # pragma: no cover - 调试路径
            import sys

            sys.stdout.write(text)
            sys.stdout.flush()

    def flush(self) -> None:
        pass

    @property
    def output(self) -> str:
        """目前为止的全部输出。"""
        return "".join(self._chunks)

    def take_output(self) -> str:
        """取出并清空已收集的输出。"""
        text = "".join(self._chunks)
        self._chunks.clear()
        return text

    # ---- 输入 ----------------------------------------------------------
    def feed(self, data: object) -> None:
        """把数据塞进输入队列，模拟用户按键。"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("只能喂 bytes 或 str")
        self._input.append(bytes(data))

    def read(self, timeout: float = 0.0) -> bytes:
        if self._pending:
            data = bytes(self._pending)
            self._pending.clear()
            return data
        if not self._input:
            return b""
        return self._input.popleft()

    @property
    def pending_input(self) -> int:
        return len(self._input)

    # ---- 尺寸 ----------------------------------------------------------
    def size(self) -> Tuple[int, int]:
        return self._size

    def set_size(self, width: int, height: int) -> None:
        """模拟窗口尺寸变化。"""
        self._size = clamp_size(width, height)

    def resize(self, width: int, height: int) -> None:
        self.set_size(width, height)

    def __repr__(self) -> str:
        return "MemoryBackend(%dx%d, %d writes)" % (
            self._size[0],
            self._size[1],
            self.writes,
        )
