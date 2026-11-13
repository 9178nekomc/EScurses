# EScurses

**Make games in the terminal with Python. Zero dependencies. Windows / Linux / macOS.**

> 中文文档：[README-zh.md](./README-zh.md)
> Original author: [@KID194](https://github.com/KID194) · 2.0 rewrite & test suite: [@9178nekomc](https://github.com/9178nekomc)
> Licensing / provenance: [NOTICE.md](./NOTICE.md)

---

## What it is

A pure-Python library for drawing with characters in a terminal, reading the keyboard,
and pacing frames. The goal is not to replace `curses` — it is to let someone who just
started Python ship a playable game in ten minutes, while the library quietly handles
the cross-platform parts (encoding, key sequences, terminal state restoration).

Version 1.x was a 102-line single file. 2.0 rewrites the internals **without breaking the
old API**, and adds tests, docs, and packaging.

```python
from escurses import Terminal, Style, widgets

with Terminal(title="My Game") as term:
    term.screen.put(2, 1, "Hello, world", Style(fg="bright_cyan", bold=True))
    widgets.draw_box(term.screen, 0, 0, 30, 5, title="BOX")
    term.present()
    term.read_key(timeout=None)   # press any key to exit
```

---

## Features

| | |
|---|---|
| **Cross-platform** | `msvcrt` + VT sequences on Windows, `termios` cbreak + `os.read` on POSIX |
| **No dependencies** | standard library only — copy the folder and go |
| **CJK / emoji aware** | layout by display width: wide chars take 2 columns, combining marks 0 |
| **Truecolor** | 16 / 256 / 24-bit with automatic quantization on weaker terminals |
| **Complete keyboard** | arrows, Home/End/PgUp/PgDn, F1-F12, Ctrl+arrows, Alt+char, UTF-8 |
| **Incremental rendering** | row-level diffing; first frame is ~8× smaller than 1.x |
| **Safe teardown** | alt screen, cursor, autowrap and `termios` state restored on `with` exit |
| **Resize** | detected every frame; buffer rebuilt, content preserved |
| **Headless-testable** | `MemoryBackend` lets CI run full render tests with no TTY |
| **Widgets** | boxes, word wrap, sprites, progress bars, display-width padding |
| **Typed** | full type hints + `py.typed` |

---

## Install

```bash
pip install git+https://github.com/9178nekomc/EScurses.git

# or, after cloning
pip install .
```

Or simply copy the `escurses/` folder next to your script — it is dependency-free.

Requires **Python 3.8+**.

---

## Quick start

```python
from escurses import Clock, Key, Style, Terminal, widgets

def main():
    with Terminal(title="Bounce") as term:
        clock = Clock(60)
        x, y, dx = 5, 3, 1

        while True:
            clock.tick()                     # sleep to next frame boundary
            for event in term.poll():        # drain this frame's keys
                if event.char in ("q", "Q") or event.key is Key.ESC:
                    return
            x += dx
            if x <= 1 or x >= term.width - 2:
                dx = -dx

            screen = term.screen
            screen.clear()
            widgets.draw_box(screen, 0, 0, term.width, term.height, border="round")
            screen.put(x, y, "O", Style(fg="bright_green", bold=True))
            widgets.draw_text(screen, 2, 0, " score: 0 ", Style(fg="yellow"))
            term.present()                   # flush only what changed

main()
```

### Legacy API (1.x style, still supported)

```python
import escurses as esc

esc.initGame()
while True:
    esc.frameStart()
    esc.drawChar(10, 5, "@")     # 1-based coordinates, as before
    esc.refresh()
    key = esc.getch()            # None when no key is waiting
    if key == "q":
        break
    esc.sleepForFrame(30)
esc.exitGame()
```

Nothing was removed — only the implementation changed. Three behaviour differences are
listed in the [migration notes](#migrating-from-1x).

---

## API

### `Terminal`

| Member | Description |
|---|---|
| `Terminal(backend=None, *, alt_screen=True, hide_cursor=True, clear_on_start=True, wrap=False, title=None, colors=None, on_resize=None)` | Create a session. Pass a `MemoryBackend` for headless use. |
| `start()` / `close()` | Enter / leave game mode. `close()` is idempotent and never raises. |
| `screen` | Current `Screen` buffer |
| `width` / `height` / `size` | Terminal dimensions |
| `present()` | Flush the diff; returns bytes written |
| `poll(timeout=0)` | `list[KeyEvent]` |
| `read_key(timeout=None)` | One `KeyEvent` or `None`; `None` timeout blocks forever |
| `clear()` / `force_redraw()` / `screenshot()` | Buffer clear / full repaint / text dump |
| `set_title()` / `bell()` / `show_cursor(bool)` | Misc terminal control |

### `Screen`

Coordinates are **0-based**, `(x, y) = (column, row)`.

`put(x, y, text, style)` clips out-of-bounds instead of raising; `get`, `fill`, `clear`,
`row`, `rows`, `to_text`, `resize`, `apply_resize`, `copy`.

Control characters (including `\x1b`) are replaced with `?` — the buffer will never
forward an escape sequence that came from untrusted text.

### `Style` / `Color`

```python
Style(fg="red", bg="#102030", bold=True, underline=True)
Color.named("bright_cyan")   Color.index(196)   Color.rgb(255, 136, 0)
Color.parse("#f80")          Color.parse(196)   Color.parse((255, 136, 0))
```

Styles are immutable — use `style.replace(bold=True)`. Colors degrade automatically:
truecolor → 256 → 16 → none.

### Input

```python
for event in term.poll():
    if event.key is Key.UP: ...
    if event.char == "q": ...
    if Modifiers.CTRL in event.modifiers: ...
```

`Key` subclasses `str`, so `event.key == "UP"` works too.

Keys: `CHAR ESC ENTER TAB BACKSPACE DELETE INSERT UP DOWN LEFT RIGHT HOME END PAGE_UP PAGE_DOWN SHIFT_TAB F1..F12 UNKNOWN`.

### Widgets

`draw_text`, `draw_paragraph`, `wrap_text`, `draw_box`, `draw_hline`, `draw_vline`,
`draw_sprite`, `draw_progress_bar`, `pad_text`, `center_text`.
Borders: `single`, `double`, `round`, `heavy`, `ascii`, `none`.

### `Clock`

```python
clock = Clock(60, max_dt=0.25)
dt = clock.tick()     # sleeps to the next frame boundary, returns last frame's dt
```

Sleep-first, spin-last: the kernel handles the bulk, the final ~2 ms spin absorbs the
scheduler's granularity. Falling more than a whole frame behind resets the baseline
instead of fast-forwarding to catch up. `Clock(fps, spin=False)` disables the spin.

---

## Demos

```bash
python -m escurses              # built-in snake
python -m escurses --fps 20
python examples/02_colors.py    # colour chart
python examples/05_widgets.py   # widget showcase
```

---

## Architecture

```
escurses/
├── terminal.py     session lifecycle, resize, I/O orchestration
├── screen.py       2D cell buffer (pure memory, no I/O)
├── render.py       row-level diff → minimal ANSI (pure function)
├── input.py        KeyParser: CSI / SS3 / UTF-8 state machine
├── clock.py        fixed-timestep pacer
├── color.py        Style / Color / SGR / downgrade
├── textutil.py     display width, grapheme clusters, sanitising
├── widgets.py      boxes, wrap, sprites, progress bars
├── _legacy.py      1.x functional API shim
├── demo.py         built-in snake
└── backends/
    ├── ansi.py     POSIX: termios + os.read + select
    ├── windows.py  Windows: VT enable + scancode translation
    └── memory.py   in-memory backend (tests / CI / fallback)
```

Hard rule: **nothing outside `backends/` touches the OS.** That is why the buffer,
renderer, parser and widgets are all unit-testable without a terminal — and why this
project can afford 445 tests.

---

## Tests

```bash
pip install pytest
python -m pytest            # 445 passed, 3 skipped
```

| Layer | What it covers |
|---|---|
| Unit | widths, buffer, diff renderer, SGR, key state machine, clock, widgets |
| **Virtual terminal replay** | `tests/vt.py` is a small ANSI interpreter: library output is actually *rendered* to a grid and compared cell by cell. Misalignment, runaway cursors and missing SGR resets all get caught here. |
| Fuzz | 25 seeds × 12 rounds of random edits, each verified by replay |
| Integration | a full headless game of snake, plus every example's draw function |
| Performance | output-size and zero-bytes-for-unchanged-frame assertions |
| Cross-platform | GitHub Actions on Ubuntu / Windows / macOS × Python 3.8 / 3.11 / 3.13 |

No TTY is required, so the whole suite runs in CI, containers, and over SSH.

---

## What was fixed

| # | 1.x behaviour | Consequence | 2.0 |
|---|---|---|---|
| 1 | buffer width was `screen_width - 1` | last column unDrawable, `IndexError` if you tried | autowrap disabled (`CSI ?7l`), full width usable |
| 2 | one `ESC[y;xH` per cell per frame | 1920 cursor jumps per frame at 80×24 | row diff + contiguous runs, 42 KB → 5 KB first frame |
| 3 | no bounds check in `drawChar` | sprite off-screen → crash | clips (`strict=True` restores the exception) |
| 4 | wide chars ignored | CJK/emoji misaligned, borders sheared | width-aware layout + placeholder cells, halves repaired on overwrite |
| 5 | spin condition hard-coded to `< 0.01` | fps > 100 was throttled *down*; one core pegged | waits for the real frame boundary, sleep then short spin |
| 6 | `tcsetattr` twice per `getch` | 120 syscalls/s, `TCSADRAIN` dropped typeahead | mode switched once on open/close |
| 7 | POSIX blocking read never entered cbreak | line buffered — needed Enter | cbreak (`ISIG` kept, so Ctrl-C still works) |
| 8 | `stdin.read(1)` through the text layer | arrows split into `ESC` / `[` / `A` | `os.read` on the raw fd + state machine |
| 9 | Windows `\x00`/`\xe0` prefix unhandled | arrows delivered half an event | scancodes translated to ANSI, shared parser |
| 10 | VT mode never enabled on Windows | literal `←[2J` on older conhost | `SetConsoleMode` with `ENABLE_VIRTUAL_TERMINAL_PROCESSING` |
| 11 | `subprocess.run("cls", shell=True)` | spawned a process to clear the screen; state not restored | alt-screen exit + full restore, `atexit` fallback |
| 12 | no exception safety | a crash left the cursor hidden and the terminal hosed | `with` / `try-finally` / `atexit` |
| 13 | no alt screen | game output polluted scrollback | `CSI ?1049h/l` |
| 14 | no resize handling | garbage or crash after a resize | per-frame detection, in-place rebuild |
| 15 | `clear()` lacked `ESC[H` | cursor stayed put, later drawing drifted | clear + home |
| 16 | `cursorEcho` never flushed | cursor changes could lag a frame | immediate flush |
| 17 | control chars written verbatim | any displayed external text could inject ANSI and hijack the terminal | `sanitize()` replaces them |
| 18 | non-TTY raised | unusable from pipes or IDEs | backend fallback + background stdin reader |
| 19 | no colour | monochrome games only | 16/256/truecolor with downgrade |
| 20 | not packaged | copy-the-file only | `pyproject.toml`, console entry point, `py.typed` |

---

## Migrating from 1.x

**No code changes required.** Three behaviour differences, all fixes:

1. **The last column is drawable now.** If you relied on `IndexError` to detect the
   screen edge, use `screen.width` instead.
2. **Named keys return string constants.** Pressing Up used to deliver `"\x00"` + `"H"`
   on Windows and `"\x1b"`, `"["`, `"A"` on POSIX — unusable either way. It now returns
   `"UP"`, comparable with `escurses.KEY_UP`.
3. **`getTerminalSize()` returns `(80, 24)` instead of raising `OSError` when there is no
   TTY.** Use `linuxTerminalCheck()` to detect the environment.

`exitGame()` no longer clears the screen — it leaves the alternate screen so the player
gets their scrollback back. Pass `exitGame(clear_after=True)` for the old behaviour.

---

## Known limitations

- **No mouse support.** The SGR mouse protocol behaves inconsistently on conhost;
  shipping a half-working implementation is worse than none.
- **Grapheme clustering is approximate.** Combining marks, VS16 and ZWJ sequences are
  handled; the full Unicode rule table is not (that would need a `regex` dependency).
  A few exotic emoji sequences may be measured wrong.
- **macOS is not manually verified.** CI runs the full suite on macOS (POSIX backend),
  but I have not eyeballed line endings and terminal modes on real hardware.
- **Windows requires 10 (1511+)** for VT sequences; older systems raise
  `TerminalNotSupportedError` instead of printing garbage.
- **Ctrl+arrows on Windows** covers only the four arrow keys.
- **The 2 ms spin tail** trades CPU for timing precision; disable with
  `Clock(fps, spin=False)` on battery.

---

## Roadmap

- [ ] Mouse events (POSIX first, Windows behind a flag)
- [ ] Cell-level diff instead of row-span diff
- [ ] `Sprite` / `Scene` objects for beginners
- [ ] Full Unicode grapheme clusters (optional dependency)
- [ ] Record / replay file format for scripted demos

---

## Contributing

PRs welcome — especially **tests** and **real-hardware reports**. Before submitting:

```bash
python -m pytest
python -m pyflakes escurses/
```

If you actually run this on macOS, please tell me how it went — that is the one part I
have no first-hand verification for.

---

## License

EScurses is released under the MIT License. See [LICENSE](./LICENSE) for the full text
and [NOTICE.md](./NOTICE.md) for provenance. The upstream project added its MIT license
on 2026-11-04; this fork includes that license and the original copyright notice.
