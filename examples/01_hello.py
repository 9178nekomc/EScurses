"""最小示例：在新 API 下画一屏文字并等待退出。

运行::

    python examples/01_hello.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from escurses import Clock, Key, Style, Terminal, widgets


def draw(screen, frame: int = 0) -> None:
    """画一帧。帧号用来做一点小动画。"""
    title = "Hello, EScurses!"
    widgets.center_text(
        screen, screen.height // 2 - 2, title,
        Style(fg="bright_cyan", bold=True),
    )
    widgets.center_text(
        screen, screen.height // 2, "你好，世界 こんにちは 🌏",
        Style(fg="bright_yellow"),
    )

    width = min(30, screen.width - 4)
    if width > 4:
        ratio = (frame % 60) / 59.0
        widgets.draw_progress_bar(
            screen, (screen.width - width) // 2, screen.height // 2 + 2,
            width, ratio, style=Style(fg="green"), empty_style=Style(fg="bright_black"),
        )

    widgets.center_text(
        screen, screen.height - 2, "按 Q 或 Esc 退出",
        Style(fg="bright_black"),
    )


def main() -> int:
    with Terminal(title="EScurses Hello") as term:
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
