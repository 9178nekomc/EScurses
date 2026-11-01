"""控件总览：边框、文本折行、精灵、进度条。

运行::

    python examples/05_widgets.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from escurses import Clock, Key, Style, Terminal, widgets

SHIP = [
    "  /\\  ",
    " /  \\ ",
    "/_||_\\",
]

PARAGRAPH = (
    "EScurses 是一个纯 Python 的终端游戏库，不需要任何第三方依赖。"
    "它关心三件事：把字符画对位置（包括中文和 emoji）、把按键读完整"
    "（包括方向键和组合键）、把帧率控稳（不空转 CPU）。"
)


def draw(screen, frame: int = 0) -> None:
    screen.clear()

    # 左：文本折行
    left_w = screen.width // 2 - 1
    widgets.draw_box(screen, 0, 0, left_w, screen.height,
                     border="single", title=" 折行 ")
    used = widgets.draw_paragraph(screen, 2, 2, left_w - 4, PARAGRAPH)

    # 右：精灵 + 进度条
    right_x = left_w
    right_w = screen.width - right_x
    widgets.draw_box(screen, right_x, 0, right_w, screen.height,
                     border="single", title=" 控件 ",
                     style=Style(fg="cyan"))

    widgets.draw_sprite(screen, right_x + 3, 2, SHIP,
                        Style(fg="bright_green", bold=True))

    labels = ["生命", "能量", "护盾"]
    for index, label in enumerate(labels):
        y = 7 + index * 2
        if y >= screen.height - 3:
            break
        widgets.draw_text(screen, right_x + 2, y, label, Style(fg="bright_black"))
        bar_x = right_x + 7
        bar_w = right_w - 10
        if bar_w > 4:
            ratio = (0.3 + 0.25 * index + frame * 0.01) % 1.0
            widgets.draw_progress_bar(
                screen, bar_x, y, bar_w, ratio,
                style=Style(fg="bright_green"), empty_style=Style(fg="bright_black"),
            )

    widgets.draw_text(screen, 1, screen.height - 1, "折行用了 %d 行" % used,
                      Style(fg="bright_black"))
    widgets.center_text(screen, screen.height - 1, "按 Q 退出", Style(fg="bright_black"))


def main() -> int:
    with Terminal(title="EScurses Widgets") as term:
        clock = Clock(30)
        frame = 0
        while True:
            clock.tick()
            for event in term.poll():
                if event.key is Key.ESC or event.char in ("q", "Q"):
                    return 0
            draw(term.screen, frame)
            term.present()
            frame += 1


if __name__ == "__main__":
    raise SystemExit(main())
