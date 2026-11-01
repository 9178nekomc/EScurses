"""颜色与样式总览。

运行::

    python examples/02_colors.py

如果你的终端只支持 16 色，下面的真彩色会自动量化到最接近的可用颜色。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from escurses import Clock, Key, Style, Terminal, get_color_support, widgets

BASIC = [
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow",
    "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
]


def draw(screen, frame: int = 0) -> None:
    support = get_color_support()
    widgets.draw_box(screen, 0, 0, screen.width, screen.height,
                     border="round", title=" COLORS ")

    row = 1
    widgets.draw_text(screen, 2, row, "16 色：", Style(bold=True))
    for index, name in enumerate(BASIC):
        x = 9 + index * 3
        if x + 2 >= screen.width:
            break
        screen.put(x, row, "██", Style(fg=name))
    row += 2

    widgets.draw_text(screen, 2, row, "256 色：", Style(bold=True))
    row += 1
    per_row = max(1, (screen.width - 4) // 4)
    for index in range(256):
        x = 2 + (index % per_row) * 4
        y = row + index // per_row
        if y >= screen.height - 4:
            break
        screen.put(x, y, "██", Style(bg=index))
    row += (256 + per_row - 1) // per_row + 1

    if row < screen.height - 4:
        widgets.draw_text(screen, 2, row, "真彩渐变：", Style(bold=True))
        width = min(screen.width - 4, 60)
        for column in range(width):
            red = int(255 * column / max(1, width - 1))
            screen.put(2 + column, row + 1, "█",
                       Style(fg=(red, 80, 255 - red)))

    widgets.draw_text(
        screen, 2, screen.height - 3,
        "色彩能力：%s" % support.name, Style(fg="bright_black"),
    )
    widgets.draw_text(
        screen, 2, screen.height - 2,
        "粗体 斜体 下划线 反显 删除线",
        Style(bold=True, italic=True, underline=True),
    )
    widgets.center_text(screen, screen.height - 1, "按 Q 退出", Style(fg="bright_black"))


def main() -> int:
    with Terminal(title="EScurses Colors") as term:
        clock = Clock(10)
        while True:
            clock.tick()
            for event in term.poll():
                if event.key is Key.ESC or event.char in ("q", "Q"):
                    return 0
            draw(term.screen)
            term.present()


if __name__ == "__main__":
    raise SystemExit(main())
