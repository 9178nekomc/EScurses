"""性能回归测试。

不追求绝对耗时（CI 机器性能差异太大），而是守住两条**确定性**指标：

1. 同样的画面，新渲染器输出的字节数必须比"逐格绝对定位"的老做法少一个数量级；
2. 无改动的帧必须产出 0 字节。
"""

from __future__ import annotations

import time

import pytest

from escurses import Screen, Style, set_color_support
from escurses.render import render
from vt import VirtualTerminal

WIDTH, HEIGHT = 120, 40


@pytest.fixture(autouse=True)
def truecolor():
    set_color_support("truecolor")
    yield
    set_color_support(None)


def legacy_render_size(screen: Screen) -> int:
    """旧版 refresh() 的输出规模：每个格子一条定位序列。"""
    total = 0
    for y in range(screen.height):
        for x in range(screen.width):
            cell = screen.get(x, y)
            if cell[0] == "":
                continue
            total += len("\x1b[%d;%dH" % (y + 1, x + 1)) + len(cell[0])
    return total


def paint(screen: Screen) -> None:
    """高频换色的画面：几乎每格样式都不同，是渲染器最不利的情况。"""
    for y in range(screen.height):
        for x in range(screen.width):
            if (x * 7 + y * 3) % 11 == 0:
                screen.put(x, y, "█", Style(fg="green"))
            elif (x + y) % 17 == 0:
                screen.put(x, y, "中", Style(fg="yellow", bold=True))


def paint_sparse(screen: Screen) -> None:
    """真实游戏里的常见画面：大片空白，零星几段文字。"""
    for y in range(2, screen.height - 2, 4):
        screen.put(2, y, "Hello, 世界", Style(fg="cyan"))


def test_sparse_frame_is_order_of_magnitude_smaller():
    """大片空白的首帧（刚清过屏，空白行整行跳过）—— 这才是数量级的差距。"""
    screen = Screen(WIDTH, HEIGHT)
    paint_sparse(screen)
    new_size = len(render(None, screen, assume_blank=True))
    old_size = legacy_render_size(screen)
    assert new_size * 10 < old_size, (new_size, old_size)


def test_blank_row_skipping_is_safe():
    """跳过空白行不能影响正确性。"""
    screen = Screen(WIDTH, HEIGHT)
    paint_sparse(screen)
    vt = VirtualTerminal(WIDTH, HEIGHT)
    vt.feed(render(None, screen, assume_blank=True))
    assert vt.mismatches(screen) == []


def test_dense_frame_still_wins():
    """每格都换样式是渲染器最不利的情况，但也必须仍然更省。"""
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    new_size = len(render(None, screen))
    old_size = legacy_render_size(screen)
    assert new_size * 3 < old_size, (new_size, old_size)


def test_sixty_animation_frames_are_cheap():
    """一个小球移动 60 帧，总输出量必须远小于 60 次全量重绘。"""
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    front = [screen.row(y) for y in range(screen.height)]
    screen.clear_dirty()

    total = 0
    for frame in range(60):
        x = frame % (WIDTH - 2)
        screen.put(x, 20, "O", Style(fg="red"))
        if x:
            screen.put(x - 1, 20, " ")
        total += len(render(front, screen))
        front = [screen.row(y) for y in range(screen.height)]
        screen.clear_dirty()

    full_frame = len(render(None, screen))
    assert total < full_frame, (total, full_frame)


def test_unchanged_frame_costs_nothing():
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    front = [screen.row(y) for y in range(screen.height)]
    screen.clear_dirty()
    assert render(front, screen) == ""


def test_small_update_is_small():
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    front = [screen.row(y) for y in range(screen.height)]
    screen.clear_dirty()
    screen.put(60, 20, "!")
    out = render(front, screen)
    assert len(out) < 30
    assert "!" in out


def test_rendering_a_large_frame_is_fast():
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    start = time.perf_counter()
    for _ in range(20):
        screen.clear_dirty()
        screen.mark_all_dirty()
        render(None, screen)
    elapsed = time.perf_counter() - start
    # 20 帧 120x40 全量渲染，阈值放得很松，只用来抓性能灾难
    assert elapsed < 5.0, "渲染过慢：%.3fs" % elapsed


def test_diff_rendering_beats_full_redraw():
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    front = [screen.row(y) for y in range(screen.height)]
    screen.clear_dirty()
    screen.put(0, 0, "X")
    incremental = render(front, screen)
    full = render(None, screen)
    assert len(incremental) * 100 < len(full)


def test_output_still_renders_correctly_under_load():
    screen = Screen(WIDTH, HEIGHT)
    paint(screen)
    vt = VirtualTerminal(WIDTH, HEIGHT)
    vt.feed(render(None, screen))
    assert vt.mismatches(screen) == []
