"""旧版函数式 API 的兼容层。

第 5 版及以前，这个库只有十几个全局函数（``initGame`` / ``drawChar`` /
``refresh`` ...）。已经用它写了游戏的人不该因为升级而重写代码，所以这些
函数全部保留，行为尽量不变，只修掉内部的实现缺陷：

===============  ====================================================
函数              修正内容
===============  ====================================================
``initGame``     缓冲区不再少一列；重复调用变成幂等
``clear``        补发 ``ESC[H``，光标回到左上角
``drawChar``     越界不再 IndexError（改为裁剪，``strict`` 模式可还原）
``refresh``      改成行级 diff，一帧输出量减少一个数量级
``getch``        方向键/F1-F12 返回具名按键；UTF-8 不再被拆碎；
                 不再每帧 ``tcsetattr`` 两次
``cursorEcho``   补上 flush，立即生效
``exitGame``     不再 fork 子进程清屏；退出备用屏幕、恢复终端状态
``sleepForFrame``修正自旋条件，fps > 100 时不再反被拖慢
``getTerminalSize`` 非 TTY 环境不再抛 OSError，退回 80x24
===============  ====================================================
"""

from __future__ import annotations

import sys
from typing import Optional

from . import clock as _clock
from .exceptions import TerminalStateError
from .input import Key, KeyEvent
from .screen import Screen
from .terminal import ANSI, Terminal

__all__ = [
    "initGame",
    "clear",
    "drawChar",
    "refresh",
    "getch",
    "getkey",
    "cursorEcho",
    "exitGame",
    "shutdown",
    "frameStart",
    "sleepForFrame",
    "getTerminalSize",
    "linuxTerminalCheck",
    "getScreen",
    "KEY_UP",
    "KEY_DOWN",
    "KEY_LEFT",
    "KEY_RIGHT",
    "KEY_ENTER",
    "KEY_ESC",
    "KEY_SPACE",
    "KEY_BACKSPACE",
    "KEY_TAB",
    "KEY_HOME",
    "KEY_END",
    "KEY_PAGE_UP",
    "KEY_PAGE_DOWN",
    "KEY_DELETE",
    "KEY_INSERT",
    "KEY_F1",
    "KEY_F2",
    "KEY_F3",
    "KEY_F4",
    "KEY_F5",
    "KEY_F6",
    "KEY_F7",
    "KEY_F8",
    "KEY_F9",
    "KEY_F10",
    "KEY_F11",
    "KEY_F12",
]

# ---- 供旧代码直接访问的内部变量（保持名字不变） ---------------------------
_terminal: Optional[Terminal] = None
_screen: Optional[Screen] = None
_screenWidth: Optional[int] = None
_screenHeight: Optional[int] = None
#: 当前 Terminal 是否由 ``initGame()`` 创建的"完整会话"
_full_session = False

# ---- getch() 的返回值常量 -------------------------------------------------
# 旧版按方向键只能拿到 "\x1b" / "\xe0"，现在返回这些名字，
# 于是可以写 `if ch == escurses.KEY_UP:`
KEY_UP = Key.UP.value
KEY_DOWN = Key.DOWN.value
KEY_LEFT = Key.LEFT.value
KEY_RIGHT = Key.RIGHT.value
KEY_ENTER = Key.ENTER.value
KEY_ESC = Key.ESC.value
KEY_SPACE = " "
KEY_BACKSPACE = Key.BACKSPACE.value
KEY_TAB = Key.TAB.value
KEY_HOME = Key.HOME.value
KEY_END = Key.END.value
KEY_PAGE_UP = Key.PAGE_UP.value
KEY_PAGE_DOWN = Key.PAGE_DOWN.value
KEY_DELETE = Key.DELETE.value
KEY_INSERT = Key.INSERT.value
KEY_F1 = Key.F1.value
KEY_F2 = Key.F2.value
KEY_F3 = Key.F3.value
KEY_F4 = Key.F4.value
KEY_F5 = Key.F5.value
KEY_F6 = Key.F6.value
KEY_F7 = Key.F7.value
KEY_F8 = Key.F8.value
KEY_F9 = Key.F9.value
KEY_F10 = Key.F10.value
KEY_F11 = Key.F11.value
KEY_F12 = Key.F12.value


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------

def initGame(**kwargs) -> Screen:
    """初始化游戏屏幕。

    重复调用是幂等的 —— 旧版重复调用会重建缓冲区，把已经画好的东西
    悄悄清掉，是个很容易踩的坑。
    """
    global _terminal, _screen, _screenWidth, _screenHeight, _full_session
    if _terminal is not None and _terminal.started and _full_session:
        return _screen  # type: ignore[return-value]

    if _terminal is not None:
        # 之前可能被 getch() 建过一个轻量会话，升级成完整会话前先收尾
        _terminal.close()
        _terminal = None

    terminal_kwargs = dict(kwargs)
    terminal_kwargs.setdefault("title", "EScurses")
    _terminal = Terminal(**terminal_kwargs)
    _terminal.start()
    _screen = _terminal.screen
    _screenWidth, _screenHeight = _screen.size
    _full_session = True
    return _screen


def getScreen() -> Screen:
    """返回当前屏幕缓冲区，未初始化时先初始化。"""
    if _screen is None:
        return initGame()
    return _screen


def shutdown() -> None:
    """恢复终端状态但不退出进程。可重复调用。"""
    global _terminal, _screen, _screenWidth, _screenHeight, _full_session
    if _terminal is not None:
        _terminal.close()
        _terminal = None
    _screen = None
    _screenWidth = None
    _screenHeight = None
    _full_session = False


def exitGame(code: int = 0, *, clear_after: bool = False) -> None:
    """退出游戏。

    旧版是用 ``subprocess.run("cls", shell=True)`` 清屏的，这里改成
    退出终端备用屏幕 —— 效果是玩家退出后会看回自己原来的终端内容，
    而不是被塞进一个空白窗口。

    :param clear_after: 关闭备用屏幕后再清一次屏（想要旧版效果时打开）
    """
    shutdown()
    if clear_after:
        try:
            sys.stdout.write(ANSI.CLEAR)
            sys.stdout.flush()
        except (ValueError, OSError):  # pragma: no cover
            pass
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# 绘制
# ---------------------------------------------------------------------------

def clear() -> None:
    """清屏并立刻把光标移回左上角。"""
    screen = getScreen()
    screen.clear()
    # 旧版只发 ESC[2J，光标留在原地，后面 refresh 会从奇怪的位置开始画
    term = _terminal
    if term is not None and term.started:
        term.backend.write(ANSI.CLEAR)
        term.backend.flush()
    else:  # pragma: no cover - 理论上走不到
        sys.stdout.write(ANSI.CLEAR)
        sys.stdout.flush()


def drawChar(x: int, y: int, char: str) -> None:
    """在 ``(x, y)`` 写字。坐标从 **1** 开始，与旧版一致。"""
    if not isinstance(x, int) or not isinstance(y, int):
        raise TypeError("drawChar 的坐标必须是整数")
    if not isinstance(char, str):
        raise TypeError("drawChar 的第三个参数必须是字符串")
    if char == "":
        return
    getScreen().put(x - 1, y - 1, char)


def refresh() -> None:
    """把缓冲区刷到终端。"""
    if _terminal is None or not _terminal.started:
        raise TerminalStateError("refresh() 之前必须先调用 initGame()")
    _terminal.present()


def cursorEcho(echo: bool = False) -> None:
    """显示 / 隐藏光标。

    .. note::
       参数名是历史包袱：``echo=False`` 表示**隐藏**光标。新代码请用
       ``terminal.show_cursor(True/False)``。
    """
    sequence = ANSI.CURSOR_SHOW if echo else ANSI.CURSOR_HIDE
    if _terminal is not None and _terminal.started:
        _terminal.show_cursor(echo)
    else:
        sys.stdout.write(sequence)
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# 输入
# ---------------------------------------------------------------------------

def getch(nodelay: bool = True):
    """读一个按键，返回字符串；``nodelay=True`` 时没有按键返回 ``None``。

    可打印字符原样返回单字符字符串；方向键、F1-F12 等返回
    :data:`KEY_UP` 这类常量。想要完整的键名、修饰符和原始字节，
    请用 :func:`getkey`。
    """
    event = getkey(nodelay=nodelay)
    if event is None:
        return None
    return _legacy_char(event)


def getkey(nodelay: bool = True, timeout: Optional[float] = None) -> Optional[KeyEvent]:
    """读一个按键，返回 :class:`~escurses.input.KeyEvent`。"""
    terminal = _ensure_terminal()
    if nodelay and timeout is None:
        timeout = 0.0
    return terminal.read_key(timeout)


def _legacy_char(event: KeyEvent) -> str:
    if event.char is not None:
        return event.char
    return event.key.value


def _ensure_terminal() -> Terminal:
    """保证有一个可读输入的终端，但不抢占屏幕、不隐藏光标。"""
    global _terminal, _full_session
    if _terminal is not None and _terminal.started:
        return _terminal
    if _terminal is None:
        # 只读一次按键不该把玩家的屏幕切走，所以用"轻量会话"
        _terminal = Terminal(alt_screen=False, clear_on_start=False, hide_cursor=False)
        _terminal.start()
        _full_session = False
    return _terminal


# ---------------------------------------------------------------------------
# 帧率与环境
# ---------------------------------------------------------------------------

def frameStart() -> float:
    """记录帧开始时刻，必须在主循环最开头调用。"""
    return _clock.begin_frame()


def sleepForFrame(fps: float) -> float:
    """睡到本帧结束，把帧率压到 ``fps``。

    返回本帧耗时（秒）。旧版会无条件忙等把 CPU 打满，这里改成
    "先睡再短自旋"，同时修正了 fps > 100 时被强行拖慢的问题。
    """
    return _clock.end_frame(fps)


def getTerminalSize():
    """返回 ``(列, 行)``。非 TTY 环境下退回 80x24，不再抛异常。"""
    if _terminal is not None and _terminal.started:
        return _terminal.size
    try:
        import shutil

        columns, lines = shutil.get_terminal_size((80, 24))
    except OSError:  # pragma: no cover
        columns, lines = (80, 24)
    return (int(columns), int(lines))


def linuxTerminalCheck() -> bool:
    """stdin 是否连接着真实终端。

    名字里的 ``linux`` 是历史遗留 —— 它在 macOS 上同样有效。
    """
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, ValueError, OSError):  # pragma: no cover
        return False
