"""帧率控制测试。

全部使用假时钟，不真的 sleep —— 测试必须跑得快，而且不能依赖
机器负载（否则 CI 上必然偶发失败）。
"""

from __future__ import annotations

import pytest

from escurses import clock as clock_module
from escurses.clock import Clock


class FakeTime:
    """可注入的时间源。"""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake():
    return FakeTime()


def make_clock(fake, fps=60.0, **kwargs):
    kwargs.setdefault("spin", False)
    return Clock(fps, clock=fake.clock, sleep=fake.sleep, **kwargs)


class TestConstruction:
    def test_frame_time(self):
        assert Clock(50).frame_time == pytest.approx(0.02)

    @pytest.mark.parametrize("fps", [0, -1, -0.5])
    def test_invalid_fps(self, fps):
        with pytest.raises(ValueError):
            Clock(fps)

    def test_delta_initially_zero(self):
        assert Clock(60).delta == 0.0


class TestTick:
    def test_first_tick_does_not_sleep(self, fake):
        clk = make_clock(fake)
        assert clk.tick() == 0.0
        assert fake.sleeps == []

    def test_steady_state_sixty_fps(self, fake):
        clk = make_clock(fake, 60)
        clk.tick()
        deltas = [clk.tick() for _ in range(10)]
        for delta in deltas:
            assert delta == pytest.approx(1 / 60, rel=1e-6)
        assert fake.now == pytest.approx(10 / 60)

    def test_work_time_is_subtracted_from_sleep(self, fake):
        clk = make_clock(fake, 100)
        clk.tick()
        fake.now += 0.004  # 模拟本帧干了 4ms 的活
        delta = clk.tick()
        assert delta == pytest.approx(0.01)  # 两次 tick 之间隔了一个整帧
        # 只需要再补 6ms
        assert fake.sleeps[-1] == pytest.approx(0.006)

    def test_overlong_frame_resets_instead_of_catching_up(self, fake):
        clk = make_clock(fake, 60)
        clk.tick()
        fake.now += 5.0  # 断点停在这里了
        delta = clk.tick()
        assert delta == pytest.approx(clk._max_dt)
        assert fake.sleeps == []  # 已经落后，不该再睡
        # 落后时允许补一帧不睡，之后回到稳态
        clk.tick()
        before = fake.now
        clk.tick()
        assert fake.now - before == pytest.approx(1 / 60)

    def test_reset(self, fake):
        clk = make_clock(fake, 60)
        clk.tick()
        clk.reset()
        assert clk.tick() == 0.0


class TestSpin:
    def test_spin_terminates(self):
        """自旋必须在时钟前进后结束，不能死循环。"""

        class TickingClock:
            """每次读时钟都前进一点，模拟真实 perf_counter。"""

            def __init__(self):
                self.now = 0.0

            def clock(self):
                self.now += 0.0002
                return self.now

            def sleep(self, seconds):
                self.now += max(0.0, seconds) + 0.0005

        ticking = TickingClock()
        clk = Clock(120, spin=True, spin_margin=0.002,
                    clock=ticking.clock, sleep=ticking.sleep)
        clk.tick()
        clk.tick()
        assert ticking.now > 0

    def test_spin_has_safety_valve(self):
        """注入不前进的时钟时，自旋必须靠迭代上限退出。"""

        class FrozenClock:
            def clock(self):
                return 100.0

            def sleep(self, seconds):
                pass

        frozen = FrozenClock()
        clk = Clock(60, spin=True, spin_margin=0.002,
                    clock=frozen.clock, sleep=frozen.sleep)
        # 不挂死就是通过
        clk._wait_until(100.001)

    def test_no_spin_uses_plain_sleep(self, fake):
        clk = make_clock(fake, 30, spin=False)
        clk.tick()
        clk.tick()
        assert fake.sleeps == [pytest.approx(1 / 30)]


class TestSleepFor:
    def test_sleep_for(self, fake):
        clk = make_clock(fake)
        clk.sleep_for(0.5)
        assert fake.now == pytest.approx(0.5)

    def test_sleep_for_zero(self, fake):
        clk = make_clock(fake)
        clk.sleep_for(0)
        assert fake.sleeps == []


class TestLegacyFrame:
    def test_begin_end(self, monkeypatch):
        fake = FakeTime()
        monkeypatch.setattr(clock_module.time, "perf_counter", fake.clock)
        monkeypatch.setattr(
            clock_module,
            "_legacy_clock",
            Clock(60, spin=False, clock=fake.clock, sleep=fake.sleep),
        )
        clock_module.begin_frame()
        elapsed = clock_module.end_frame(120)
        assert elapsed == pytest.approx(1 / 120)

    def test_end_without_begin_does_not_crash(self, monkeypatch):
        fake = FakeTime()
        monkeypatch.setattr(clock_module.time, "perf_counter", fake.clock)
        monkeypatch.setattr(
            clock_module,
            "_legacy_clock",
            Clock(60, spin=False, clock=fake.clock, sleep=fake.sleep),
        )
        clock_module._frame_begin = None
        # 没有 begin 时退化为"直接睡一帧"，而不是像旧版抛 TypeError
        assert clock_module.end_frame(60) == pytest.approx(1 / 60)

    def test_zero_fps_is_tolerated(self, monkeypatch):
        fake = FakeTime()
        monkeypatch.setattr(clock_module.time, "perf_counter", fake.clock)
        monkeypatch.setattr(
            clock_module,
            "_legacy_clock",
            Clock(60, spin=False, clock=fake.clock, sleep=fake.sleep),
        )
        clock_module.begin_frame()
        assert clock_module.end_frame(0) >= 0
