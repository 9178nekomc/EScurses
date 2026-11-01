"""集成测试：无头跑完整程序，用虚拟终端验证真实画面。

这是最有价值的一层测试 —— 单元测试能证明"每个零件对"，只有这一层能证明
"装起来真的能玩"。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from escurses import Key, KeyEvent, MemoryBackend, Terminal
from escurses.demo import SnakeGame, run
from vt import VirtualTerminal

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def load_example(name: str):
    path = EXAMPLES / name
    spec = importlib.util.spec_from_file_location("example_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def headless():
    backend = MemoryBackend(40, 12)
    terminal = Terminal(backend, title="test")
    terminal.start()
    yield terminal, backend
    terminal.close()


class TestDemoRuns:
    def test_runs_n_frames_and_quits(self, headless):
        terminal, backend = headless
        keys = [None] * 3 + [KeyEvent(Key.CHAR, "q")]
        run(terminal, fps=1000, max_frames=8, seed=7, scripted_keys=keys)
        vt = VirtualTerminal(*terminal.size)
        vt.feed(backend.output)
        assert vt.mismatches(terminal.screen) == []

    def test_snake_moves(self, headless):
        terminal, _backend = headless
        game = SnakeGame(40, 12, seed=1)
        start = game.snake[0]
        for _ in range(3):
            game.update()
        assert game.snake[0] != start

    def test_snake_eats_food(self, headless):
        game = SnakeGame(40, 12, seed=1)
        head = game.snake[0]
        game.food = (head[0] + 1, head[1])
        before = game.score
        game.update()
        assert game.score == before + 10
        assert len(game.snake) == 4

    def test_snake_wall_collision(self):
        game = SnakeGame(40, 12, seed=1)
        for _ in range(100):
            game.update()
            if game.dead:
                break
        assert game.dead

    def test_snake_cannot_reverse(self):
        game = SnakeGame(40, 12, seed=1)
        game.handle(KeyEvent(Key.LEFT))
        game.update()
        assert game.direction != (-1, 0)

    def test_pause(self):
        game = SnakeGame(40, 12, seed=1)
        game.handle(KeyEvent(Key.CHAR, " "))
        snapshot = list(game.snake)
        game.update()
        assert list(game.snake) == snapshot

    def test_restart_after_death(self):
        game = SnakeGame(40, 12, seed=1)
        game.dead = True
        game.score = 120
        game.handle(KeyEvent(Key.CHAR, "r"))
        assert not game.dead
        assert game.score == 0

    def test_quit_key(self):
        game = SnakeGame(40, 12)
        assert game.handle(KeyEvent(Key.CHAR, "q")) is True

    def test_too_small_terminal(self):
        backend = MemoryBackend(10, 4)
        terminal = Terminal(backend)
        terminal.start()
        try:
            score = run(terminal, fps=1000, max_frames=2)
            assert score == 0
            assert "窗口太小" in terminal.screenshot()
        finally:
            terminal.close()

    def test_survives_theoretical_long_run(self, headless):
        terminal, _backend = headless
        run(terminal, fps=1000, max_frames=60, seed=3)
        assert terminal.started


class TestExamples:
    @pytest.mark.parametrize(
        "name",
        [
            "01_hello.py",
            "02_colors.py",
            "05_widgets.py",
        ],
    )
    def test_example_exports_draw(self, name):
        module = load_example(name)
        assert callable(module.draw)

    @pytest.mark.parametrize(
        "name",
        ["01_hello.py", "02_colors.py", "05_widgets.py"],
    )
    def test_example_draws_correctly(self, name, headless):
        terminal, backend = headless
        module = load_example(name)
        module.draw(terminal.screen, 0)
        terminal.present()
        vt = VirtualTerminal(*terminal.size)
        vt.feed(backend.output)
        assert vt.mismatches(terminal.screen) == []
        assert vt.text().strip(), "示例应该画出内容"

    def test_legacy_example_draws(self, headless):
        terminal, backend = headless
        module = load_example("04_legacy.py")

        import escurses

        escurses.shutdown()
        escurses.initGame(backend=backend)
        try:
            module.draw(escurses.getScreen())
            escurses.refresh()
            vt = VirtualTerminal(*terminal.size)
            vt.feed(backend.output)
            text = vt.text()
            assert text.count("-") > 10
            assert "|" in text
        finally:
            escurses.shutdown()

    def test_all_examples_are_importable(self):
        for path in sorted(EXAMPLES.glob("*.py")):
            load_example(path.name)
