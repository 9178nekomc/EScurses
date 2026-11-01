"""EScurses —— 用 Python 在终端里做游戏。

两套 API 并存：

**旧 API（函数式，保持兼容）**::

    import escurses as esc

    esc.initGame()
    while True:
        esc.frameStart()
        esc.drawChar(10, 5, "@")
        esc.refresh()
        key = esc.getch()
        if key == "q":
            esc.exitGame()
        esc.sleepForFrame(60)

**新 API（对象式，推荐）**::

    from escurses import Terminal, Style, Color, widgets

    with Terminal() as term:
        clock = Clock(60)
        while True:
            dt = clock.tick()
            for event in term.poll():
                if event.char == "q":
                    raise SystemExit
            screen = term.screen
            widgets.draw_box(screen, 0, 0, 30, 5, Style(fg="cyan"), title="HELLO")
            term.present()
"""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "KID194 <original author>, 9178nekomc <maintainer>"
__license__ = "MIT"

from . import widgets
from .backends import AnsiBackend, Backend, MemoryBackend, WindowsBackend, create_backend
from .clock import Clock
from .color import (
    BLACK,
    BLUE,
    BRIGHT_BLACK,
    BRIGHT_BLUE,
    BRIGHT_CYAN,
    BRIGHT_GREEN,
    BRIGHT_MAGENTA,
    BRIGHT_RED,
    BRIGHT_WHITE,
    BRIGHT_YELLOW,
    CYAN,
    GREEN,
    MAGENTA,
    RED,
    WHITE,
    YELLOW,
    Color,
    ColorSupport,
    Style,
    detect_support,
    get_color_support,
    set_color_support,
)
from .exceptions import (
    EscursesError,
    ScreenBoundsError,
    TerminalNotSupportedError,
    TerminalStateError,
)
from .input import Key, KeyEvent, KeyParser, Modifiers
from .render import render, render_full
from .screen import Screen
from .terminal import ANSI, Terminal
from .textutil import char_width, sanitize, text_width, truncate
from .widgets import (
    draw_box,
    draw_hline,
    draw_paragraph,
    draw_progress_bar,
    draw_sprite,
    draw_text,
    draw_vline,
    fill_rect,
    pad_text,
    wrap_text,
)

# 旧版函数式 API（写在最后，保证新名字优先）
from . import _legacy
from ._legacy import (
    KEY_BACKSPACE,
    KEY_DELETE,
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_ESC,
    KEY_F1,
    KEY_F2,
    KEY_F3,
    KEY_F4,
    KEY_F5,
    KEY_F6,
    KEY_F7,
    KEY_F8,
    KEY_F9,
    KEY_F10,
    KEY_F11,
    KEY_F12,
    KEY_HOME,
    KEY_INSERT,
    KEY_LEFT,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_TAB,
    KEY_UP,
    clear,
    cursorEcho,
    drawChar,
    exitGame,
    frameStart,
    getch,
    getkey,
    getScreen,
    getTerminalSize,
    initGame,
    linuxTerminalCheck,
    refresh,
    shutdown,
    sleepForFrame,
)

__all__ = [
    # 版本
    "__version__",
    # 核心对象
    "Terminal",
    "Screen",
    "Clock",
    "ANSI",
    # 输入
    "Key",
    "KeyEvent",
    "KeyParser",
    "Modifiers",
    # 样式
    "Style",
    "Color",
    "ColorSupport",
    "detect_support",
    "get_color_support",
    "set_color_support",
    "BLACK",
    "RED",
    "GREEN",
    "YELLOW",
    "BLUE",
    "MAGENTA",
    "CYAN",
    "WHITE",
    "BRIGHT_BLACK",
    "BRIGHT_RED",
    "BRIGHT_GREEN",
    "BRIGHT_YELLOW",
    "BRIGHT_BLUE",
    "BRIGHT_MAGENTA",
    "BRIGHT_CYAN",
    "BRIGHT_WHITE",
    # 后端
    "Backend",
    "AnsiBackend",
    "WindowsBackend",
    "MemoryBackend",
    "create_backend",
    # 渲染
    "render",
    "render_full",
    # 文本
    "char_width",
    "text_width",
    "truncate",
    "sanitize",
    # 控件
    "widgets",
    "draw_text",
    "draw_paragraph",
    "draw_box",
    "draw_hline",
    "draw_vline",
    "draw_sprite",
    "draw_progress_bar",
    "fill_rect",
    "pad_text",
    "wrap_text",
    # 异常
    "EscursesError",
    "TerminalNotSupportedError",
    "TerminalStateError",
    "ScreenBoundsError",
    # 旧 API
    "initGame",
    "getScreen",
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


def __getattr__(name: str):
    """把 ``escurses._screen`` 这类旧代码访问的内部变量转发到兼容层。

    兼容层里的 ``_screen`` 会随着 ``initGame()`` / ``shutdown()`` 重新绑定，
    如果在这里拷贝一份就会失去同步，所以必须动态转发。
    """
    if name in ("_screen", "_screenWidth", "_screenHeight", "_terminal"):
        return getattr(_legacy, name)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
