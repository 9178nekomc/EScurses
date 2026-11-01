"""把缓冲区差异渲染成最小 ANSI 字节流。

旧实现每帧对每个格子发一次 ``ESC[row;colH``，80x24 就是 1920 次绝对定位，
在慢终端上肉眼可见地卡。这里的做法是：

1. 只处理"脏行"（本帧被写过的行）；
2. 每一行只找**首个不同**和**末个不同**的单元格，中间整段连续输出；
3. 样式只在变化时发一条 SGR，行与行之间不重复发送。

一帧的典型输出量从 ~15KB 降到几百字节。
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .screen import Cell, Screen

__all__ = ["render", "render_full"]


def _cursor(row: int, col: int) -> str:
    """1-based 光标定位序列。"""
    return "\x1b[%d;%dH" % (row, col)


def _diff_span(old_row: Sequence[Cell], new_row: Sequence[Cell]) -> Tuple[int, int]:
    """返回 ``(start, end)``，两者相等表示整行没变。"""
    length = len(new_row)
    start = length
    for x in range(length):
        if old_row[x] != new_row[x]:
            start = x
            break
    if start == length:
        return (length, length)
    end = start + 1
    for x in range(length - 1, start, -1):
        if old_row[x] != new_row[x]:
            end = x + 1
            break
    return (start, end)


def render(
    front: Optional[List[List[Cell]]],
    screen: Screen,
    full: bool = False,
    assume_blank: bool = False,
) -> str:
    """生成从 ``front`` 到 ``screen`` 的增量更新序列。

    :param front: 上一帧的逐行快照；``None`` 表示没有历史，整屏重绘。
    :param screen: 当前缓冲区。
    :param full: 强制整屏重绘（窗口尺寸变化后必须这么做）。
    :param assume_blank: 终端当前确实是空白（刚清过屏）。此时可以整行跳过
        空白行，首帧输出量能再降一个数量级。
    """
    if front is None:
        full = True
        if screen.width < 1 or screen.height < 1:  # pragma: no cover - 构造时已校验
            return ""

    blank = screen.blank_cell
    out: List[str] = []
    last_body = "0"

    for y in range(screen.height):
        if not full and y not in screen.dirty_rows:
            continue
        new_row = screen.row(y)
        if full:
            if assume_blank and all(cell == blank for cell in new_row):
                continue
            start, end = 0, screen.width
        else:
            start, end = _diff_span(front[y], new_row)
            if start == end:
                continue

        # 不能从宽字符的后半截开始写，否则终端会把前面那半格当成孤儿
        while start > 0 and new_row[start][0] == "":
            start -= 1
        if start >= end:
            continue

        out.append(_cursor(y + 1, start + 1))

        for x in range(start, end):
            text, body = new_row[x]
            if text == "":
                # 宽字符的后半截：终端在画前半截时已经占用了这一列
                continue
            if body != last_body:
                out.append("\x1b[" + body + "m")
                last_body = body
            out.append(text)

    if last_body != "0":
        out.append("\x1b[0m")
    return "".join(out)


def render_full(screen: Screen) -> str:
    """整屏重绘，等价于 ``render(None, screen)``。"""
    return render(None, screen, full=True)
