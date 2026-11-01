"""按键解析。

终端输入本质上是一条字节流：方向键发的是 ``ESC [ A`` 这样的 CSI 序列，
中文发的是多字节 UTF-8，单独按一下 Esc 又和"某个 CSI 序列的前缀"无法区分。
旧实现直接 ``read(1)`` 读一个字符就返回，结果方向键被拆成 ``\\x1b``、
``[``、``A`` 三次事件，游戏里根本没法用。

这里用一个状态机把字节流还原成 :class:`KeyEvent`：

* 完整的 CSI / SS3 序列 → 具名按键（方向键、F1-F12、Home/End/...）；
* 组合键修饰符（``ESC[1;5A`` = Ctrl+↑）→ :class:`Modifiers`；
* UTF-8 多字节字符 → 正常的 :class:`Key.CHAR`；
* 孤立的 Esc → 等待 ``esc_timeout`` 后判定为 Esc 键，而不是吞掉。
"""

from __future__ import annotations

import time
from enum import Enum, IntFlag
from typing import List, Optional, Tuple

__all__ = ["Key", "Modifiers", "KeyEvent", "KeyParser"]


class Key(str, Enum):
    """具名按键。

    继承 ``str``，所以 ``Key.UP == "UP"`` 成立 —— 旧代码里写
    ``if ch == "UP"`` 也能用。
    """

    CHAR = "CHAR"
    ESC = "ESC"
    ENTER = "ENTER"
    TAB = "TAB"
    BACKSPACE = "BACKSPACE"
    DELETE = "DELETE"
    INSERT = "INSERT"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    HOME = "HOME"
    END = "END"
    PAGE_UP = "PAGE_UP"
    PAGE_DOWN = "PAGE_DOWN"
    SHIFT_TAB = "SHIFT_TAB"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"
    UNKNOWN = "UNKNOWN"


class Modifiers(IntFlag):
    NONE = 0
    SHIFT = 1
    ALT = 2
    CTRL = 4

    def __str__(self) -> str:  # pragma: no cover - 仅用于展示
        if self == Modifiers.NONE:
            return "NONE"
        names = [name for name in ("CTRL", "ALT", "SHIFT") if self & getattr(Modifiers, name)]
        return "+".join(names)

    @classmethod
    def from_csi(cls, value: int) -> "Modifiers":
        """CSI 的修饰符参数是 1 + 位掩码（1=Shift, 2=Alt, 4=Ctrl）。"""
        return cls(max(0, value - 1))


class KeyEvent:
    """一次按键事件。"""

    __slots__ = ("key", "char", "modifiers", "raw")

    def __init__(
        self,
        key: Key,
        char: Optional[str] = None,
        modifiers: Modifiers = Modifiers.NONE,
        raw: bytes = b"",
    ) -> None:
        self.key = Key(key)
        self.char = char
        self.modifiers = Modifiers(modifiers)
        self.raw = raw

    # ---- 便捷判断 ------------------------------------------------------
    @property
    def is_printable(self) -> bool:
        """是否是可直接当文本用的字符（不含 Ctrl 组合）。"""
        return self.key is Key.CHAR and bool(self.char) and not (self.modifiers & Modifiers.CTRL)

    @property
    def name(self) -> str:
        return self.key.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KeyEvent):
            return NotImplemented
        return (
            self.key == other.key
            and self.char == other.char
            and self.modifiers == other.modifiers
        )

    def __hash__(self) -> int:
        return hash((self.key, self.char, self.modifiers))

    def __str__(self) -> str:
        if self.char is not None:
            return self.char
        return self.key.value

    def __repr__(self) -> str:
        bits = ["key=%s" % self.key.value]
        if self.char is not None:
            bits.append("char=%r" % (self.char,))
        if self.modifiers:
            bits.append("modifiers=%s" % (self.modifiers,))
        return "KeyEvent(%s)" % ", ".join(bits)


#: ``ESC [ <n> ~`` 形式的特殊键
_TILDE_KEYS = {
    1: Key.HOME,
    2: Key.INSERT,
    3: Key.DELETE,
    4: Key.END,
    5: Key.PAGE_UP,
    6: Key.PAGE_DOWN,
    7: Key.HOME,
    8: Key.END,
    11: Key.F1,
    12: Key.F2,
    13: Key.F3,
    14: Key.F4,
    15: Key.F5,
    17: Key.F6,
    18: Key.F7,
    19: Key.F8,
    20: Key.F9,
    21: Key.F10,
    23: Key.F11,
    24: Key.F12,
}

_FINAL_KEYS = {
    "A": Key.UP,
    "B": Key.DOWN,
    "C": Key.RIGHT,
    "D": Key.LEFT,
    "E": Key.HOME,
    "F": Key.END,
    "H": Key.HOME,
    "P": Key.F1,
    "Q": Key.F2,
    "R": Key.F3,
    "S": Key.F4,
    "Z": Key.SHIFT_TAB,
}

#: 控制字符 → (键, 伴随字符)。``None`` 表示该字节单独成键。
_CONTROL_KEYS = {
    0x00: (Key.CHAR, "\x00"),
    0x08: (Key.BACKSPACE, "\x08"),
    0x09: (Key.TAB, "\t"),
    0x0A: (Key.ENTER, "\n"),
    0x0D: (Key.ENTER, "\r"),
    0x7F: (Key.BACKSPACE, "\x7f"),
}


class KeyParser:
    """把字节流解析成 :class:`KeyEvent`。

    解析器是**有状态**的：一个 CSI 序列可能分几次 ``feed`` 才到齐，
    所以必须复用同一个实例。
    """

    __slots__ = ("_buf", "_last_data", "_esc_timeout", "_clock")

    #: 单独按 Esc 时，等多久没有后续字节就认定是 Esc 键
    DEFAULT_ESC_TIMEOUT = 0.06

    def __init__(self, esc_timeout: float = DEFAULT_ESC_TIMEOUT, clock=time.monotonic) -> None:
        self._buf = bytearray()
        self._last_data = 0.0
        self._esc_timeout = float(esc_timeout)
        self._clock = clock

    @property
    def pending(self) -> bytes:
        """当前还没能解析完的字节（调试用）。"""
        return bytes(self._buf)

    def reset(self) -> None:
        self._buf.clear()

    # ------------------------------------------------------------------
    def feed(self, data: bytes) -> List[KeyEvent]:
        """喂入字节，返回本次能解析出的所有事件。"""
        if not data:
            return []
        self._buf.extend(data)
        self._last_data = self._clock()
        return self._drain()

    def flush(self, now: Optional[float] = None) -> List[KeyEvent]:
        """把超时未完成的序列强制落定（孤立 Esc 走这条路）。"""
        now = self._clock() if now is None else now
        if not self._buf:
            return []
        if now - self._last_data < self._esc_timeout:
            return []
        events: List[KeyEvent] = []
        # 缓冲区里卡住的一定是以 ESC 开头的残缺序列，先吐出 Esc，
        # 余下的字节重新按普通键解析。
        if self._buf[0] == 0x1B:
            events.append(KeyEvent(Key.ESC, "\x1b", raw=b"\x1b"))
            del self._buf[0]
        # 强行解析剩余字节，遇到不完整就丢弃一个
        guard = len(self._buf) + 1
        while self._buf and guard:
            guard -= 1
            event, consumed = self._parse_one()
            if event is None:
                del self._buf[0]
                continue
            events.append(event)
            del self._buf[:consumed]
        return events

    # ------------------------------------------------------------------
    def _drain(self) -> List[KeyEvent]:
        events: List[KeyEvent] = []
        while self._buf:
            event, consumed = self._parse_one()
            if event is None:
                break
            events.append(event)
            if consumed:
                del self._buf[:consumed]
        return events

    def _parse_one(self) -> Tuple[Optional[KeyEvent], int]:
        """解析缓冲区开头的按键。

        返回 ``(事件, 消耗字节数)``；事件为 ``None`` 表示数据还不完整。
        """
        buf = self._buf
        head = buf[0]
        if head == 0x1B:
            return self._parse_escape()
        return self._parse_basic(0)

    # ---- 普通键 --------------------------------------------------------
    def _parse_basic(self, offset: int) -> Tuple[Optional[KeyEvent], int]:
        buf = self._buf
        if offset >= len(buf):
            return (None, 0)
        head = buf[offset]

        if head < 0x20 or head == 0x7F:
            key, char = _CONTROL_KEYS.get(head, (Key.CHAR, chr(head)))
            modifiers = Modifiers.CTRL if (0x01 <= head <= 0x1A and head not in (0x08, 0x09, 0x0A, 0x0D)) else Modifiers.NONE
            if head == 0x00:
                modifiers = Modifiers.CTRL
            return (KeyEvent(key, char, modifiers, bytes(buf[offset:offset + 1])), offset + 1)

        if head < 0x80:
            return (KeyEvent(Key.CHAR, chr(head), Modifiers.NONE, bytes(buf[offset:offset + 1])), offset + 1)

        # UTF-8 多字节
        if 0xC2 <= head <= 0xDF:
            need = 2
        elif 0xE0 <= head <= 0xEF:
            need = 3
        elif 0xF0 <= head <= 0xF4:
            need = 4
        else:
            # 非法起始字节，吃掉它
            return (KeyEvent(Key.UNKNOWN, None, Modifiers.NONE, bytes(buf[offset:offset + 1])), offset + 1)

        if len(buf) - offset < need:
            return (None, 0)
        chunk = bytes(buf[offset:offset + need])
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return (KeyEvent(Key.UNKNOWN, None, Modifiers.NONE, chunk[:1]), offset + 1)
        return (KeyEvent(Key.CHAR, text, Modifiers.NONE, chunk), offset + need)

    # ---- 转义序列 ------------------------------------------------------
    def _parse_escape(self) -> Tuple[Optional[KeyEvent], int]:
        buf = self._buf
        if len(buf) == 1:
            return (None, 0)  # 可能只是单独按了 Esc，等超时

        second = buf[1]
        if second == 0x5B:  # '['
            return self._parse_csi()
        if second == 0x4F:  # 'O'
            if len(buf) < 3:
                return (None, 0)
            return self._ss3(chr(buf[2]), 3)
        if second == 0x1B:
            return (KeyEvent(Key.ESC, "\x1b", raw=b"\x1b"), 1)

        # Alt + 普通键：把后面的键解析出来，加上 ALT 修饰符
        event, consumed = self._parse_basic(1)
        if event is None:
            return (None, 0)
        event.modifiers |= Modifiers.ALT
        event.raw = bytes(buf[:consumed])
        return (event, consumed)

    def _parse_csi(self) -> Tuple[Optional[KeyEvent], int]:
        buf = self._buf
        index = 2
        params = bytearray()
        while index < len(buf):
            byte = buf[index]
            if 0x40 <= byte <= 0x7E:
                return self._csi(bytes(params), chr(byte), index + 1)
            if byte > 0x3F or len(params) > 24:
                # 不是合法的 CSI 参数，当作噪声丢弃 ESC
                return (KeyEvent(Key.ESC, "\x1b", raw=b"\x1b"), 1)
            params.append(byte)
            index += 1
        return (None, 0)

    def _ss3(self, final: str, consumed: int) -> Tuple[Optional[KeyEvent], int]:
        key = _FINAL_KEYS.get(final)
        raw = bytes(self._buf[:consumed])
        if key is None:
            return (KeyEvent(Key.UNKNOWN, None, Modifiers.NONE, raw), consumed)
        return (KeyEvent(key, None, Modifiers.NONE, raw), consumed)

    def _csi(self, params: bytes, final: str, consumed: int) -> Tuple[Optional[KeyEvent], int]:
        raw = bytes(self._buf[:consumed])
        if params[:1] == b"?":
            # 私有模式查询/回执（例如 "\x1b[?25h"），不是按键
            return (KeyEvent(Key.UNKNOWN, None, Modifiers.NONE, raw), consumed)

        try:
            text = params.decode("ascii")
        except UnicodeDecodeError:  # pragma: no cover - 上游已校验字节范围
            text = ""
        parts = text.split(";") if text else []

        def number(index: int, default: int = 0) -> int:
            if index >= len(parts) or not parts[index]:
                return default
            try:
                return int(parts[index])
            except ValueError:
                return default

        modifiers = Modifiers.from_csi(number(1, 1)) if len(parts) > 1 else Modifiers.NONE

        if final == "~":
            key = _TILDE_KEYS.get(number(0))
            if key is None:
                return (KeyEvent(Key.UNKNOWN, None, modifiers, raw), consumed)
            return (KeyEvent(key, None, modifiers, raw), consumed)

        key = _FINAL_KEYS.get(final)
        if key is None:
            return (KeyEvent(Key.UNKNOWN, None, modifiers, raw), consumed)
        return (KeyEvent(key, None, modifiers, raw), consumed)
