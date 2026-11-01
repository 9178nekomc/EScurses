"""帧率控制。

原版 ``sleepForFrame`` 有两个毛病：

* ``while time.perf_counter() - _frameStartTime < 0.01: pass`` —— 硬编码等
  到帧开始后 10ms，而不是等到帧结束。60fps 时这段自旋什么也没干，
  而 fps > 100 时反而会把帧拖到 10ms 以上，帧率被强行压到 100 以下。
* 无条件忙等，一核 100% 占用。

这里的 :class:`Clock` 采用"睡眠 + 末端短自旋"：

1. 先 ``sleep(剩余 - 2ms)``，把大头交给内核；
2. 最后 2ms 自旋，抹掉 ``sleep`` 的粒度误差（Windows 传统上最差 15.6ms，
   不补这一下帧率会剧烈抖动）；
3. 落后超过一帧时重置时间基准，而不是连续追帧（否则掉帧之后会疯狂快进）。
"""

from __future__ import annotations

import time
from typing import Callable, Optional

__all__ = ["Clock", "begin_frame", "end_frame", "current_fps"]


class Clock:
    """固定帧率的节拍器。

    典型用法::

        clock = Clock(60)
        while running:
            dt = clock.tick()     # 睡到下一帧边界，返回上一帧耗时（秒）
            update(dt)
            draw()
    """

    __slots__ = (
        "fps",
        "_frame_time",
        "_max_dt",
        "_spin_margin",
        "_spin",
        "_clock",
        "_sleep",
        "_last",
        "_next",
        "_dt",
        "_frames",
    )

    def __init__(
        self,
        fps: float = 60.0,
        *,
        max_dt: float = 0.25,
        spin_margin: float = 0.002,
        spin: bool = True,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        fps = float(fps)
        if fps <= 0:
            raise ValueError("fps 必须大于 0，收到 %r" % (fps,))
        self.fps = fps
        self._frame_time = 1.0 / fps
        self._max_dt = float(max_dt)
        self._spin_margin = max(0.0, float(spin_margin))
        self._spin = bool(spin)
        self._clock = clock
        self._sleep = sleep
        self._last: Optional[float] = None
        self._next = 0.0
        self._dt = 0.0
        self._frames = 0

    # ---- 属性 ----------------------------------------------------------
    @property
    def frame_time(self) -> float:
        """单帧时长（秒）。"""
        return self._frame_time

    @property
    def delta(self) -> float:
        """上一帧的耗时，已按 ``max_dt`` 截断。"""
        return self._dt

    @property
    def frames(self) -> int:
        return self._frames

    def reset(self) -> None:
        """重置时间基准（例如从暂停恢复时）。"""
        self._last = None
        self._next = 0.0
        self._dt = 0.0

    # ---- 节拍 ----------------------------------------------------------
    def tick(self) -> float:
        """等待到下一帧边界，返回上一帧耗时（秒）。第一帧返回 0。"""
        now = self._clock()
        if self._last is None:
            self._last = now
            self._next = now + self._frame_time
            self._dt = 0.0
            return 0.0

        self._wait_until(self._next)
        now = self._clock()
        raw = now - self._last
        self._last = now
        self._dt = raw if raw < self._max_dt else self._max_dt
        self._frames += 1

        self._next += self._frame_time
        if self._next < now:
            # 已经落后一个整帧以上（断点、系统卡顿），重新对齐，
            # 否则接下来会连续 sleep(0) 空转追帧
            self._next = now
        return self._dt

    def sleep_for(self, seconds: float) -> None:
        """睡眠指定时长，带末端自旋补偿。"""
        if seconds <= 0:
            return
        self._wait_until(self._clock() + seconds)

    def _wait_until(self, target: float) -> None:
        if not self._spin or self._spin_margin <= 0:
            delay = target - self._clock()
            if delay > 0:
                self._sleep(delay)
            return
        while True:
            delay = target - self._clock()
            if delay <= 0:
                return
            if delay > self._spin_margin:
                self._sleep(delay - self._spin_margin)
            else:
                # 末端自旋。加一个迭代上限当保险丝：正常时钟几十微秒就结束，
                # 万一有人注入了不前进的假时钟也不会把进程挂死。
                for _ in range(1 << 20):
                    if self._clock() >= target:
                        return
                return

    def __repr__(self) -> str:  # pragma: no cover
        return "Clock(fps=%g, frames=%d)" % (self.fps, self._frames)


# ---------------------------------------------------------------------------
# 旧 API：frameStart() / sleepForFrame(fps)
# ---------------------------------------------------------------------------

_legacy_clock = Clock(60.0)

#: 帧开始时刻，由 ``frameStart()`` 写入
_frame_begin: Optional[float] = None


def begin_frame() -> float:
    """记录帧开始时刻，返回 ``perf_counter()`` 读数。"""
    global _frame_begin
    _frame_begin = time.perf_counter()
    return _frame_begin


def end_frame(fps: float) -> float:
    """睡到本帧结束，返回本帧实际耗时（秒）。

    没调用 :func:`begin_frame` 就调用本函数时，退化为直接睡一帧，
    而不是像旧版那样抛 ``TypeError``。
    """
    global _frame_begin
    now = time.perf_counter()
    begin = _frame_begin if _frame_begin is not None else now
    _frame_begin = None
    fps = float(fps)
    if fps <= 0:
        return now - begin
    target = begin + 1.0 / fps
    _legacy_clock._wait_until(target)
    return time.perf_counter() - begin


def current_fps() -> float:
    """最近一次 ``sleepForFrame`` 对应的实际帧率参考值。"""
    return 1.0 / _legacy_clock.frame_time
