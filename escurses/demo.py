"""内置贪吃蛇 Demo。

它同时承担两个职责：

* 给刚接触这个库的人一个可以立刻跑起来、能改的完整示例；
* 充当集成测试的靶子 —— ``tests/test_integration.py`` 会在无头环境里
  用脚本化按键把整局游戏跑完，验证输入、渲染、计时、退出全都正常。

运行::

    python -m escurses
    python -m escurses --fps 20
"""

from __future__ import annotations

import random
from typing import Deque, List, Optional, Tuple
from collections import deque

from .clock import Clock
from .color import Color, Style
from .input import Key, KeyEvent
from .terminal import Terminal
from .textutil import text_width
from .widgets import draw_box, draw_progress_bar, draw_text

__all__ = ["SnakeGame", "run"]

Point = Tuple[int, int]

#: 每秒逻辑更新次数（与渲染帧率解耦，低帧率下蛇不会爬得更快）
TICK_RATE = 8.0

_UP: Point = (0, -1)
_DOWN: Point = (0, 1)
_LEFT: Point = (-1, 0)
_RIGHT: Point = (1, 0)


class SnakeGame:
    """一局贪吃蛇。"""

    def __init__(self, width: int, height: int, seed: Optional[int] = None) -> None:
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        self.reset()

    # ---- 状态 ----------------------------------------------------------
    @property
    def playfield(self) -> Tuple[int, int]:
        """可用区域（去掉边框）的宽高。"""
        return (max(0, self.width - 2), max(0, self.height - 3))

    def reset(self) -> None:
        _w, h = self.playfield
        mid_y = 1 + max(0, h // 2)
        start_x = 1 + min(3, max(0, self.width - 4))
        self.snake: Deque[Point] = deque(
            [(start_x - i, mid_y) for i in range(3)]
        )
        self.direction: Point = _RIGHT
        self.pending: Deque[Point] = deque()
        self.score = 0
        self.dead = False
        self.paused = False
        self.food: Optional[Point] = self._spawn_food()

    def _spawn_food(self) -> Optional[Point]:
        _w, h = self.playfield
        free = [
            (x, y)
            for y in range(1, 1 + h)
            for x in range(1, 1 + self.width - 2)
            if (x, y) not in self.snake
        ]
        if not free:
            return None
        return self.rng.choice(free)

    # ---- 输入 ----------------------------------------------------------
    def handle(self, event: KeyEvent) -> bool:
        """处理一个按键，返回是否请求退出。"""
        if event.key in (Key.ESC,) or event.char in ("q", "Q"):
            return True
        if event.key is Key.UP or event.char in ("w", "W"):
            self._turn(_UP)
        elif event.key is Key.DOWN or event.char in ("s", "S"):
            self._turn(_DOWN)
        elif event.key is Key.LEFT or event.char in ("a", "A"):
            self._turn(_LEFT)
        elif event.key is Key.RIGHT or event.char in ("d", "D"):
            self._turn(_RIGHT)
        elif event.char == " ":
            self.paused = not self.paused
        elif event.char in ("r", "R") and self.dead:
            self.reset()
        return False

    def _turn(self, direction: Point) -> None:
        if self.dead:
            return
        # 不能 180 度掉头（会立刻撞到自己）
        if (direction[0] == -self.direction[0] and direction[1] == -self.direction[1]):
            return
        if direction == self.direction:
            return
        # 缓冲一步，避免同一帧内连按两次绕过掉头检查
        if len(self.pending) < 2:
            self.pending.append(direction)

    # ---- 逻辑 ----------------------------------------------------------
    def update(self) -> None:
        if self.dead or self.paused:
            return
        if self.pending:
            self.direction = self.pending.popleft()

        head_x, head_y = self.snake[0]
        next_head = (head_x + self.direction[0], head_y + self.direction[1])

        field_w, field_h = self.playfield
        x, y = next_head
        if not (1 <= x <= field_w and 1 <= y <= field_h):
            self.dead = True
            return
        if next_head in self.snake and next_head != self.snake[-1]:
            self.dead = True
            return

        self.snake.appendleft(next_head)
        if next_head == self.food:
            self.score += 10
            self.food = self._spawn_food()
            if self.food is None:
                self.dead = True  # 通关了，按撞死处理
        else:
            self.snake.pop()

    # ---- 渲染 ----------------------------------------------------------
    def draw(self, screen) -> None:
        accent = Style(fg="green", bold=True)
        head_style = Style(fg="bright_green", bold=True)
        food_style = Style(fg="red", bold=True)
        dim = Style(fg="bright_black")

        screen.clear()
        draw_box(
            screen, 0, 0, self.width, self.height,
            border="single",
            title=" SNAKE ",
        )

        for index, (x, y) in enumerate(self.snake):
            screen.put(
                x, y,
                "@" if index == 0 else "o",
                head_style if index == 0 else accent,
            )

        if self.food is not None:
            screen.put(self.food[0], self.food[1], "*", food_style)

        self._draw_status(screen, accent, dim)

        if self.paused and not self.dead:
            self._overlay(screen, "PAUSED", "SPACE 继续")
        if self.dead:
            self._overlay(screen, "GAME OVER", "R 重来 / Q 退出")

    def _draw_status(self, screen, accent, dim) -> None:
        y = self.height - 2
        draw_text(screen, 2, y, "Score %d" % self.score, accent)
        draw_text(screen, 12, y, "Len %d" % len(self.snake), dim)

        hint = "WASD/方向键  Q 退出"
        hint_width = text_width(hint)
        if self.width >= hint_width + 20:
            draw_text(screen, self.width - hint_width - 2, y, hint, dim)

        bar_width = self.width - 40
        if bar_width >= 6:
            # 20 节算"长大成人"，纯粹给玩家一个目标感
            draw_progress_bar(
                screen, 24, y, bar_width, min(1.0, len(self.snake) / 20.0),
                style=Style(fg="bright_green"), empty_style=dim, bracket=False,
            )

    def _overlay(self, screen, title: str, hint: str) -> None:
        box_w = min(self.width - 2, max(text_width(title) + 8, 24))
        box_h = 5
        x = max(0, (self.width - box_w) // 2)
        y = max(0, (self.height - box_h) // 2)
        draw_box(
            screen, x, y, box_w, box_h,
            border="double",
            style=Style(fg="yellow", bold=True),
            fill_style=Style(fg="bright_white", bg=Color.index(17)),
        )
        title_x = x + max(0, (box_w - text_width(title)) // 2)
        draw_text(screen, title_x, y + 1, title, Style(fg="red", bold=True))
        hint_x = x + max(0, (box_w - text_width(hint)) // 2)
        draw_text(screen, hint_x, y + 3, hint, Style(fg="bright_white"))


def run(
    terminal: Terminal,
    *,
    fps: float = 30.0,
    max_frames: Optional[int] = None,
    seed: Optional[int] = None,
    scripted_keys: Optional[List[Optional[KeyEvent]]] = None,
) -> int:
    """跑一局贪吃蛇，返回最终得分。

    :param max_frames: 最多跑多少帧（自动化测试用；``None`` 表示不限）
    :param scripted_keys: 每帧注入一个按键事件（自动化测试用）
    """
    if terminal.width < 20 or terminal.height < 10:
        terminal.screen.clear()
        draw_text(terminal.screen, 0, 0, "窗口太小，至少需要 20x10")
        terminal.present()
        return 0

    game = SnakeGame(terminal.width, terminal.height, seed=seed)
    clock = Clock(fps)
    accumulator = 0.0
    frame = 0

    while True:
        dt = clock.tick()

        quit_requested = False
        for event in terminal.poll():
            if game.handle(event):
                quit_requested = True
        if scripted_keys:
            index = min(frame, len(scripted_keys) - 1)
            event = scripted_keys[index] if index < len(scripted_keys) else None
            if event is not None and game.handle(event):
                quit_requested = True
        if quit_requested:
            break

        accumulator += dt
        step = 1.0 / TICK_RATE
        # 单帧最多补 5 步，防止卡顿后蛇瞬移
        steps = 0
        while accumulator >= step and steps < 5:
            game.update()
            accumulator -= step
            steps += 1
        if accumulator >= step:
            accumulator = 0.0

        game.draw(terminal.screen)
        terminal.present()

        frame += 1
        if max_frames is not None and frame >= max_frames:
            break
        if game.dead and not scripted_keys:
            # 死了之后继续渲染等待玩家按键，不自动退出
            pass

    return game.score


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="escurses", description="EScurses 内置游戏演示"
    )
    parser.add_argument("--fps", type=float, default=30.0, help="渲染帧率（默认 30）")
    args = parser.parse_args(argv)

    terminal = Terminal(title="EScurses Snake")
    try:
        with terminal:
            run(terminal, fps=args.fps)
    except KeyboardInterrupt:
        pass
    return 0
