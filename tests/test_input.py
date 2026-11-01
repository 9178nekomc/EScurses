"""按键解析测试。

覆盖真实终端会发出的各类字节序列，包括被拆包的情况 ——
这是旧版 ``read(1)`` 最典型的翻车点。
"""

from __future__ import annotations

import pytest

from escurses.input import Key, KeyEvent, KeyParser, Modifiers


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def parser(clock):
    return KeyParser(esc_timeout=0.05, clock=clock)


def single(parser, data: bytes) -> KeyEvent:
    events = parser.feed(data)
    assert len(events) == 1, events
    return events[0]


class TestPrintable:
    def test_ascii(self, parser):
        event = single(parser, b"a")
        assert event.key is Key.CHAR
        assert event.char == "a"
        assert event.modifiers == Modifiers.NONE

    def test_multi_byte_utf8(self, parser):
        event = single(parser, "中".encode("utf-8"))
        assert event.char == "中"

    def test_emoji(self, parser):
        event = single(parser, "🐍".encode("utf-8"))
        assert event.char == "🐍"

    def test_several_keys_at_once(self, parser):
        events = parser.feed(b"abc")
        assert [e.char for e in events] == ["a", "b", "c"]

    def test_split_utf8_across_feeds(self, parser):
        data = "中".encode("utf-8")
        assert parser.feed(data[:1]) == []
        assert parser.feed(data[1:2]) == []
        events = parser.feed(data[2:])
        assert len(events) == 1 and events[0].char == "中"


class TestControlKeys:
    @pytest.mark.parametrize(
        "data,key",
        [
            (b"\r", Key.ENTER),
            (b"\n", Key.ENTER),
            (b"\t", Key.TAB),
            (b"\x7f", Key.BACKSPACE),
            (b"\x08", Key.BACKSPACE),
        ],
    )
    def test_named(self, parser, data, key):
        assert single(parser, data).key is key

    def test_ctrl_c(self, parser):
        event = single(parser, b"\x03")
        assert event.char == "\x03"
        assert Modifiers.CTRL in event.modifiers

    def test_ctrl_letter(self, parser):
        event = single(parser, b"\x1a")
        assert event.char == "\x1a"
        assert Modifiers.CTRL in event.modifiers


class TestCSI:
    @pytest.mark.parametrize(
        "data,key",
        [
            (b"\x1b[A", Key.UP),
            (b"\x1b[B", Key.DOWN),
            (b"\x1b[C", Key.RIGHT),
            (b"\x1b[D", Key.LEFT),
            (b"\x1b[H", Key.HOME),
            (b"\x1b[F", Key.END),
            (b"\x1b[Z", Key.SHIFT_TAB),
            (b"\x1b[2~", Key.INSERT),
            (b"\x1b[3~", Key.DELETE),
            (b"\x1b[5~", Key.PAGE_UP),
            (b"\x1b[6~", Key.PAGE_DOWN),
            (b"\x1b[15~", Key.F5),
            (b"\x1b[17~", Key.F6),
            (b"\x1b[24~", Key.F12),
        ],
    )
    def test_arrows_and_specials(self, parser, data, key):
        assert single(parser, data).key is key

    def test_split_sequence(self, parser):
        assert parser.feed(b"\x1b") == []
        assert parser.feed(b"[") == []
        events = parser.feed(b"A")
        assert len(events) == 1 and events[0].key is Key.UP

    def test_modifiers(self, parser):
        event = single(parser, b"\x1b[1;5A")
        assert event.key is Key.UP
        assert event.modifiers == Modifiers.CTRL

    def test_shift_alt(self, parser):
        event = single(parser, b"\x1b[1;4C")
        assert event.key is Key.RIGHT
        assert event.modifiers == (Modifiers.SHIFT | Modifiers.ALT)

    def test_private_mode_is_ignored(self, parser):
        # 终端对 ESC[?25h 之类查询的回复不是按键，不能污染输入流
        assert parser.feed(b"\x1b[?25h") == [KeyEvent(Key.UNKNOWN)]

    def test_unknown_sequence(self, parser):
        event = single(parser, b"\x1b[99~")
        assert event.key is Key.UNKNOWN


class TestSS3:
    @pytest.mark.parametrize(
        "data,key",
        [
            (b"\x1bOP", Key.F1),
            (b"\x1bOQ", Key.F2),
            (b"\x1bOR", Key.F3),
            (b"\x1bOS", Key.F4),
        ],
    )
    def test_fkeys(self, parser, data, key):
        assert single(parser, data).key is key


class TestEscape:
    def test_lone_escape_needs_timeout(self, parser, clock):
        assert parser.feed(b"\x1b") == []
        clock.advance(0.01)
        assert parser.flush() == []
        clock.advance(0.1)
        events = parser.flush()
        assert len(events) == 1 and events[0].key is Key.ESC

    def test_double_escape(self, parser):
        event = single(parser, b"\x1b\x1b")
        assert event.key is Key.ESC

    def test_alt_key(self, parser):
        event = single(parser, b"\x1bx")
        assert event.char == "x"
        assert Modifiers.ALT in event.modifiers

    def test_alt_survives_encoding(self, parser):
        event = single(parser, b"\x1b" + "中".encode("utf-8"))
        assert event.char == "中"
        assert Modifiers.ALT in event.modifiers

    def test_escape_then_arrow(self, parser):
        events = parser.feed(b"\x1b")
        assert events == []
        events = parser.feed(b"[B")
        assert len(events) == 1 and events[0].key is Key.DOWN


class TestRobustness:
    def test_invalid_utf8(self, parser):
        event = single(parser, b"\xff")
        assert event.key is Key.UNKNOWN

    def test_no_infinite_loop_on_garbage(self, parser):
        events = parser.feed(b"\x1b[" + b"9" * 40)
        assert isinstance(events, list)

    def test_reset(self, parser):
        parser.feed(b"\x1b")
        parser.reset()
        assert parser.pending == b""

    def test_empty_feed(self, parser):
        assert parser.feed(b"") == []

    def test_flush_with_empty_buffer(self, parser, clock):
        clock.advance(1.0)
        assert parser.flush() == []


class TestKeyEvent:
    def test_str_prefers_char(self):
        assert str(KeyEvent(Key.CHAR, "a")) == "a"
        assert str(KeyEvent(Key.UP)) == "UP"

    def test_is_printable(self):
        assert KeyEvent(Key.CHAR, "a").is_printable
        assert not KeyEvent(Key.CHAR, "\x03", Modifiers.CTRL).is_printable
        assert not KeyEvent(Key.UP).is_printable

    def test_equality_ignores_raw(self):
        left = KeyEvent(Key.CHAR, "a", raw=b"a")
        right = KeyEvent(Key.CHAR, "a", raw=b"\x00")
        assert left == right

    def test_key_compares_to_string(self):
        # 老代码写 ch == "UP" 也应该成立
        assert Key.UP == "UP"
