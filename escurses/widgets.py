"""常用绘制控件。

全部是**纯函数**：接收 :class:`~escurses.screen.Screen` 和坐标，返回
绘制结果，不持有任何状态。这样控件可以被单独测试，也不会跟缓冲区
生命周期纠缠。

坐标系与 ``Screen`` 一致：**0-based，(x, y) = (列, 行)**。
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from .screen import Screen
from .textutil import char_width, clusters, sanitize, text_width, truncate

__all__ = [
    "BORDERS",
    "draw_text",
    "draw_paragraph",
    "wrap_text",
    "draw_box",
    "draw_hline",
    "draw_vline",
    "draw_sprite",
    "draw_progress_bar",
    "pad_text",
    "center_text",
    "fill_rect",
]

#: 可用边框样式：``(左上, 横, 右上, 竖, 右下, 横, 左下, 竖)``
BORDERS = {
    "single": ("┌", "─", "┐", "│", "┘", "─", "└", "│"),
    "double": ("╔", "═", "╗", "║", "╝", "═", "╚", "║"),
    "round": ("╭", "─", "╮", "│", "╯", "─", "╰", "│"),
    "heavy": ("┏", "━", "┓", "┃", "┛", "━", "┗", "┃"),
    "ascii": ("+", "-", "+", "|", "+", "-", "+", "|"),
    "none": (" ", " ", " ", " ", " ", " ", " ", " "),
}


# ---------------------------------------------------------------------------
# 文本
# ---------------------------------------------------------------------------

def draw_text(
    screen: Screen,
    x: int,
    y: int,
    text: str,
    style: object = None,
    max_width: Optional[int] = None,
) -> int:
    """画一行文本，返回文本结束处的列坐标（方便接着画）。"""
    if max_width is not None:
        text = truncate(sanitize(text), max_width)
    return x + screen.put(x, y, text, style)


def wrap_text(text: str, width: int) -> List[str]:
    """按显示宽度折行，兼顾中英文。

    * 英文按单词断行，不会把 ``hello`` 拆成 ``hel`` / ``lo``；
    * 中文每个字符都可以断行（CJK 本来就没有词间空格）；
    * 单个单词比整行还宽时才硬切。
    """
    if width <= 0:
        return []
    lines: List[str] = []
    for paragraph in text.split("\n"):
        line: List[str] = []
        used = 0
        for token in _tokenize(paragraph):
            token_width = text_width(token)
            if used + token_width <= width:
                line.append(token)
                used += token_width
                continue
            if token.strip() == "":
                # 断行处的空格丢掉，避免行尾悬挂
                lines.append("".join(line).rstrip())
                line, used = [], 0
                continue
            if line:
                lines.append("".join(line).rstrip())
                line, used = [], 0
            if token_width > width:
                pieces = _hard_split(token, width)
                lines.extend(pieces[:-1])
                line = [pieces[-1]] if pieces else []
                used = text_width(line[0]) if line else 0
            else:
                line.append(token)
                used = token_width
        lines.append("".join(line).rstrip())
    return lines


def draw_paragraph(
    screen: Screen,
    x: int,
    y: int,
    width: int,
    text: str,
    style: object = None,
    max_lines: Optional[int] = None,
) -> int:
    """在矩形宽度内折行绘制，返回占用的行数。"""
    lines = wrap_text(text, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    for index, line in enumerate(lines):
        screen.put(x, y + index, line, style)
    return len(lines)


def pad_text(text: str, width: int, align: str = "left") -> str:
    """按**显示宽度**补齐到指定列数。"""
    current = text_width(text)
    if current >= width:
        return truncate(text, width)
    padding = " " * (width - current)
    if align == "right":
        return padding + text
    if align == "center":
        left = (width - current) // 2
        return " " * left + text + " " * (width - current - left)
    return text + padding


def center_text(
    screen: Screen,
    y: int,
    text: str,
    style: object = None,
    width: Optional[int] = None,
) -> int:
    """在给定行居中画文本，返回**起始列**。"""
    total = screen.width if width is None else width
    start = max(0, (total - text_width(text)) // 2)
    draw_text(screen, start, y, text, style)
    return start


# ---------------------------------------------------------------------------
# 图形
# ---------------------------------------------------------------------------

def fill_rect(
    screen: Screen,
    x: int,
    y: int,
    width: int,
    height: int,
    char: str = " ",
    style: object = None,
) -> None:
    """填充矩形区域（``Screen.fill`` 的别名，语义更直观）。"""
    screen.fill(x, y, width, height, char, style)


def draw_hline(
    screen: Screen,
    x: int,
    y: int,
    length: int,
    char: str = "─",
    style: object = None,
) -> None:
    if length > 0:
        screen.fill(x, y, length, 1, char, style)


def draw_vline(
    screen: Screen,
    x: int,
    y: int,
    length: int,
    char: str = "│",
    style: object = None,
) -> None:
    if length > 0:
        screen.fill(x, y, 1, length, char, style)


def draw_box(
    screen: Screen,
    x: int,
    y: int,
    width: int,
    height: int,
    style: object = None,
    border: str = "single",
    title: Optional[str] = None,
    title_style: object = None,
    fill_style: object = None,
) -> None:
    """画一个带可选标题的边框。

    宽度或高度小于 2 时直接返回（画不出框），不会写出半截图形。
    """
    if width < 2 or height < 2:
        return
    chars = BORDERS.get(border)
    if chars is None:
        raise ValueError(
            "未知边框样式 %r，可用：%s" % (border, ", ".join(sorted(BORDERS)))
        )
    (top_left, top, top_right, side, bottom_right, bottom, bottom_left, _v) = chars

    if fill_style is not None:
        screen.fill(x, y, width, height, " ", fill_style)

    # 四角
    screen.put(x, y, top_left, style)
    screen.put(x + width - 1, y, top_right, style)
    screen.put(x, y + height - 1, bottom_left, style)
    screen.put(x + width - 1, y + height - 1, bottom_right, style)

    draw_hline(screen, x + 1, y, width - 2, top, style)
    draw_hline(screen, x + 1, y + height - 1, width - 2, bottom, style)
    draw_vline(screen, x, y + 1, height - 2, side, style)
    draw_vline(screen, x + width - 1, y + 1, height - 2, side, style)

    if title:
        inner = width - 2
        label = truncate(sanitize(title), max(0, inner - 2))
        if label and inner >= 2:
            start = x + 1 + max(0, (inner - text_width(label)) // 2)
            draw_text(screen, start, y, label, style if title_style is None else title_style)


def draw_sprite(
    screen: Screen,
    x: int,
    y: int,
    rows: Sequence[str],
    style: object = None,
) -> None:
    """把一组字符串当成精灵画出来。

    空格会被跳过 —— 精灵里的空白通常代表"透明"，直接覆盖会把背景擦掉。
    """
    for dy, row in enumerate(rows):
        cursor = x
        for chunk, width in clusters(sanitize(row)):
            if chunk != " ":
                screen.put(cursor, y + dy, chunk, style)
            cursor += width


def draw_progress_bar(
    screen: Screen,
    x: int,
    y: int,
    width: int,
    ratio: float,
    style: object = None,
    empty_style: object = None,
    bracket: bool = True,
) -> None:
    """画一条进度条，``ratio`` 会被夹到 0.0-1.0。"""
    if width <= 0:
        return
    ratio = 0.0 if ratio != ratio else min(1.0, max(0.0, float(ratio)))  # NaN 归零
    if bracket:
        inner = width - 2
        if inner <= 0:
            draw_hline(screen, x, y, width, "─", style)
            return
        screen.put(x, y, "█", style)
        screen.put(x + width - 1, y, "█", style)
        filled = int(round(inner * ratio))
        if filled:
            screen.fill(x + 1, y, filled, 1, "█", style)
        if inner - filled:
            screen.fill(x + 1 + filled, y, inner - filled, 1, "░", empty_style)
    else:
        filled = int(round(width * ratio))
        if filled:
            screen.fill(x, y, filled, 1, "█", style)
        if width - filled:
            screen.fill(x + filled, y, width - filled, 1, "░", empty_style)


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """切成"不可再分的最小断行单元"：单词、单个空格、单个宽字符。"""
    tokens: List[str] = []
    buffer: List[str] = []

    def flush() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for ch in text:
        if ch == " ":
            flush()
            tokens.append(" ")
        elif char_width(ch) == 2:
            flush()
            tokens.append(ch)
        elif char_width(ch) == 0:
            # 零宽字符跟随前一个字符
            if buffer:
                buffer.append(ch)
            elif tokens:
                tokens[-1] += ch
        else:
            buffer.append(ch)
    flush()
    return tokens


def _hard_split(token: str, width: int) -> List[str]:
    """把超宽 token 按列数硬切。"""
    pieces: List[str] = []
    current: List[str] = []
    used = 0
    for chunk, chunk_width in clusters(token):
        if used + chunk_width > width and current:
            pieces.append("".join(current))
            current, used = [], 0
        current.append(chunk)
        used += chunk_width
    if current:
        pieces.append("".join(current))
    return pieces
