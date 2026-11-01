"""旧 API 示例：和 1.x 的写法一模一样。

运行::

    python examples/04_legacy.py

这段代码在旧版 EScurses 上能跑，在新版上同样能跑 —— 但新版修掉了
"最右边一列画不了"、"方向键收不到"、"fps 高于 100 被拖慢"这些问题。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import escurses as esc

# 一个在框里弹来弹去的小球
_ball = {"x": 5, "y": 3, "dx": 1, "dy": 1}


def draw(screen) -> None:
    width, height = esc.getTerminalSize()
    esc.clear()

    # 画边框
    for x in range(1, width + 1):
        esc.drawChar(x, 1, "-")
        esc.drawChar(x, height, "-")
    for y in range(1, height + 1):
        esc.drawChar(1, y, "|")
        esc.drawChar(width, y, "|")

    ball = _ball
    ball["x"] += ball["dx"]
    ball["y"] += ball["dy"]
    if ball["x"] <= 2 or ball["x"] >= width - 1:
        ball["dx"] = -ball["dx"]
    if ball["y"] <= 2 or ball["y"] >= height - 1:
        ball["dy"] = -ball["dy"]

    esc.drawChar(ball["x"], ball["y"], "O")
    esc.cursorEcho(False)


def main() -> int:
    esc.initGame()
    try:
        while True:
            esc.frameStart()
            draw(esc.getScreen())
            esc.refresh()

            key = esc.getch()
            if key == "q" or key == esc.KEY_ESC:
                break
            esc.sleepForFrame(30)
    except KeyboardInterrupt:
        pass
    finally:
        esc.exitGame()


if __name__ == "__main__":
    main()
