"""随机化一致性测试（fuzz）。

思路：随机地往缓冲区里乱涂乱画，每次都用真实输出喂给虚拟终端，
然后逐格对比。这一层能抓到所有"只在特定操作顺序下出现"的渲染 bug ——
比如宽字符被覆盖一半、样式没复位、增量更新漏擦旧内容。

用固定种子，失败可复现。
"""

from __future__ import annotations

import random

import pytest

from escurses import Screen, Style, set_color_support
from escurses.render import render
from vt import VirtualTerminal

WIDTH, HEIGHT = 30, 10

GLYPHS = ["a", "B", "#", "─", "│", "中", "文", "🐍", "❤\ufe0f", " ", "░", "█"]
STYLES = [None, Style(), Style(bold=True), Style(fg="red"), Style(bg="blue"),
          Style(fg="#ff8800", underline=True)]


@pytest.fixture(autouse=True)
def truecolor():
    set_color_support("truecolor")
    yield
    set_color_support(None)


def mutate(rng: random.Random, screen: Screen, rounds: int) -> None:
    for _ in range(rounds):
        action = rng.random()
        if action < 0.6:
            screen.put(rng.randrange(WIDTH), rng.randrange(HEIGHT),
                       rng.choice(GLYPHS), rng.choice(STYLES))
        elif action < 0.78:
            screen.fill(rng.randrange(WIDTH), rng.randrange(HEIGHT),
                        rng.randint(1, 8), rng.randint(1, 4),
                        rng.choice(GLYPHS), rng.choice(STYLES))
        elif action < 0.9:
            screen.put(rng.randrange(WIDTH), rng.randrange(HEIGHT),
                       rng.choice(["中文测试", "hello", "🐍🐍", "mixed 混排"]),
                       rng.choice(STYLES))
        else:
            screen.clear()


@pytest.mark.parametrize("seed", range(25))
def test_random_operations_stay_consistent(seed):
    rng = random.Random(seed)
    screen = Screen(WIDTH, HEIGHT)
    vt = VirtualTerminal(WIDTH, HEIGHT)
    front = None

    for step in range(12):
        mutate(rng, screen, rng.randint(1, 15))
        output = render(front, screen)
        vt.feed(output)
        problems = vt.mismatches(screen)
        assert problems == [], "seed=%d step=%d: %r" % (seed, step, problems[:2])
        front = [screen.row(y) for y in range(screen.height)]
        screen.clear_dirty()

        # 没有新的改动时，增量输出必须是空的
        assert render(front, screen) == ""


@pytest.mark.parametrize("seed", range(10))
def test_full_redraw_always_correct(seed):
    rng = random.Random(1000 + seed)
    screen = Screen(WIDTH, HEIGHT)
    mutate(rng, screen, 60)
    vt = VirtualTerminal(WIDTH, HEIGHT)
    vt.feed(render(None, screen))
    assert vt.mismatches(screen) == []


def test_incremental_output_never_larger_than_full():
    rng = random.Random(42)
    screen = Screen(WIDTH, HEIGHT)
    mutate(rng, screen, 30)
    full = render(None, screen)
    front = [screen.row(y) for y in range(screen.height)]
    screen.clear_dirty()
    screen.put(0, 0, "x")
    incremental = render(front, screen)
    assert len(incremental) < len(full)


def test_wide_char_never_leaves_orphan():
    screen = Screen(10, 1)
    screen.put(0, 0, "中")
    screen.put(1, 0, "x")
    vt = VirtualTerminal(10, 1)
    vt.feed(render(None, screen))
    assert vt.mismatches(screen) == []
