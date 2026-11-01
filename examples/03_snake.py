"""内置贪吃蛇（直接复用库里的 demo 模块）。

运行::

    python examples/03_snake.py

想改游戏逻辑？看 ``escurses/demo.py``，全部逻辑都在那儿，
一共两百来行，改坏了也不影响库本身。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from escurses.demo import main

if __name__ == "__main__":
    raise SystemExit(main())
