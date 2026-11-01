"""pytest 公共夹具。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import escurses  # noqa: E402
from escurses import MemoryBackend, Terminal  # noqa: E402
from vt import VirtualTerminal  # noqa: E402


@pytest.fixture(autouse=True)
def clean_legacy_state():
    """每个用例结束后把兼容层的全局状态收拾干净。"""
    yield
    escurses.shutdown()


@pytest.fixture
def backend():
    return MemoryBackend(40, 12)


@pytest.fixture
def session(backend):
    """返回 ``(terminal, virtual_terminal)``，两块屏幕尺寸一致。"""
    terminal = Terminal(backend, title="test")
    terminal.start()
    vt = VirtualTerminal(*terminal.size)
    vt.feed(backend.take_output())
    yield terminal, vt
    terminal.close()
