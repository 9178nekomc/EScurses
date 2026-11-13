# EScurses

**用 Python 在终端里写游戏。零第三方依赖，Windows / Linux / macOS 通用。**

> English version: [README.md](./README.md)
> 原始作者：[@KID194](https://github.com/KID194) · 2.0 重构与测试：[@9178nekomc](https://github.com/9178nekomc)
> 授权与来源说明见 [NOTICE.md](./NOTICE.md)

---

## 这是什么

EScurses 是一个纯 Python 的终端游戏库：用字符画画面、读键盘、控帧率。
它的目标不是替代 `curses`，而是**让一个刚学 Python 的人十分钟内做出能跑的游戏**，
同时把跨平台的那些坑（编码、按键序列、终端状态恢复）在库里处理干净。

1.x 是一个 102 行的单文件。2.0 在**保留全部旧 API** 的前提下重写了内部实现，
并补上了测试、文档和打包。

```python
from escurses import Terminal, Style, widgets

with Terminal(title="My Game") as term:
    term.screen.put(2, 1, "Hello, 世界", Style(fg="bright_cyan", bold=True))
    widgets.draw_box(term.screen, 0, 0, 30, 5, title="BOX")
    term.present()
    term.read_key(timeout=None)   # 按任意键退出
```

---

## 特性

| 能力 | 说明 |
|---|---|
| **跨平台** | Windows 用 `msvcrt` + 开启 VT 序列；POSIX 用 `termios` cbreak + `os.read` |
| **零依赖** | 只用标准库，下载即用，不需要 pip 装任何东西 |
| **中文 / emoji 对齐** | 按显示宽度排版，汉字占 2 列、组合符占 0 列，边框不会被挤歪 |
| **真彩色** | 16 / 256 / 24 位三档，能力不足时自动量化降级 |
| **完整的按键** | 方向键、Home/End/PgUp/PgDn、F1-F12、Ctrl+方向键、Alt+字符、UTF-8 字符 |
| **增量渲染** | 行级 diff，只重画变了的部分；首帧输出量比旧版少 8 倍 |
| **正确恢复终端** | 备用屏幕、光标、自动换行、`termios` 状态全部在 `with` 退出时还原 |
| **窗口缩放** | 自动检测尺寸变化，重建缓冲区并保内容，不崩不花屏 |
| **无头可测** | 内置 `MemoryBackend`，CI 里没有终端也能跑完整渲染测试 |
| **控件** | 边框、折行、精灵、进度条、按宽度补齐 |
| **类型标注** | 全量 type hints + `py.typed` |

---

## 安装

三种方式，选一种：

```bash
# 1) 直接从仓库装（推荐）
pip install git+https://github.com/9178nekomc/EScurses.git

# 2) 克隆后本地装
git clone https://github.com/9178nekomc/EScurses.git
cd EScurses && pip install .
```

```text
# 3) 最省事：把 escurses/ 整个文件夹复制到你的代码目录里
你的项目/
├── escurses/        ← 复制这个文件夹
└── my_game.py       ← 然后 import escurses 就能用
```

要求 **Python 3.8+**，无第三方依赖。

---

## 快速开始

### 新 API（推荐）

```python
from escurses import Clock, Key, Style, Terminal, widgets

def main():
    with Terminal(title="Bounce") as term:
        clock = Clock(60)
        x, y, dx = 5, 3, 1

        while True:
            clock.tick()                     # 睡到下一帧边界
            for event in term.poll():        # 取走这一帧的按键
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
            term.present()                   # 只把变化的部分刷出去

main()
```

### 旧 API（1.x 写法，完全兼容）

```python
import escurses as esc

esc.initGame()
while True:
    esc.frameStart()
    esc.drawChar(10, 5, "@")     # 坐标从 1 开始，和以前一样
    esc.refresh()
    key = esc.getch()            # 无按键返回 None
    if key == "q":
        break
    esc.sleepForFrame(30)
esc.exitGame()
```

旧函数一个都没删，只修了实现。行为变化只有三处，见下文[「从 1.x 迁移」](#从-1x-迁移)。

---

## API 参考

### `Terminal`

游戏会话。**必须** 用 `with` 或手动 `start()` / `close()` 包住。

| 成员 | 说明 |
|---|---|
| `Terminal(backend=None, *, alt_screen=True, hide_cursor=True, clear_on_start=True, wrap=False, title=None, colors=None, on_resize=None)` | 创建会话。`backend` 可传 `MemoryBackend` 做无头测试 |
| `start()` / `close()` | 进入 / 退出游戏模式。`close()` 幂等且不抛异常 |
| `screen` | 当前 `Screen` 缓冲区 |
| `width` / `height` / `size` | 终端尺寸 |
| `present()` | 把差异刷到终端，返回写出的字符数 |
| `poll(timeout=0)` | 返回 `list[KeyEvent]` |
| `read_key(timeout=None)` | 返回一个 `KeyEvent` 或 `None`；`None` 表示一直等 |
| `clear()` | 清空缓冲区（下次 `present()` 生效） |
| `force_redraw()` | 丢弃快照，强制整屏重绘 |
| `screenshot()` | 导出纯文本，调试/测试用 |
| `set_title()` / `bell()` / `show_cursor(bool)` | 标题、响铃、光标 |
| `is_tty` / `is_degraded` / `supports_color` | 环境状态 |

### `Screen` —— 缓冲区

坐标是 **0-based** 的 `(x, y) = (列, 行)`。

| 方法 | 说明 |
|---|---|
| `put(x, y, text, style=None)` | 画文本，返回实际列数。越界裁剪，不抛异常 |
| `get(x, y)` / `char_at(x, y)` | 读单元格 |
| `fill(x, y, w, h, ch, style)` | 填充矩形 |
| `clear()` | 全屏空格 |
| `row(y)` / `rows()` / `to_text()` | 逐行读取 / 导出文本 |
| `resize(w, h)` / `apply_resize(w, h)` | 返回新缓冲区 / 就地调整（保持对象身份） |
| `copy()` | 深拷贝 |

控制字符（含 `\x1b`）会被替换成 `?` —— **缓冲区绝不会把外部文本里的转义序列原样送进终端**。

### `Style` / `Color`

```python
Style(fg="red", bg="#102030", bold=True, underline=True)
Color.named("bright_cyan")   Color.index(196)   Color.rgb(255, 136, 0)
Color.parse("#f80")          Color.parse(196)   Color.parse((255, 136, 0))
```

样式不可变，改样式用 `style.replace(bold=True)`。
颜色会按终端能力自动降级：真彩 → 256 → 16 → 无色。

预设：`RED` `GREEN` `YELLOW` `BLUE` `MAGENTA` `CYAN` `WHITE` 及 `BRIGHT_*`。

### 输入

```python
for event in term.poll():
    print(event.key, event.char, event.modifiers)

if event.key is Key.UP: ...
if event.char == "q": ...
if Modifiers.CTRL in event.modifiers: ...
```

`Key` 继承 `str`，所以 `event.key == "UP"` 也成立。

可用键：`CHAR ESC ENTER TAB BACKSPACE DELETE INSERT UP DOWN LEFT RIGHT HOME END PAGE_UP PAGE_DOWN SHIFT_TAB F1..F12 UNKNOWN`
修饰符：`Modifiers.SHIFT / ALT / CTRL`（可组合）

旧 API 的 `getch()` 对具名键返回字符串常量，例如 `esc.KEY_UP == "UP"`。

### 控件 `escurses.widgets`

```python
draw_text(screen, x, y, text, style, max_width)      # 返回结束列
draw_paragraph(screen, x, y, width, text, style)     # 折行，返回行数
wrap_text(text, width)                               # 中英文混排折行
draw_box(screen, x, y, w, h, style, border="single", title=None)
draw_hline / draw_vline / draw_sprite / draw_progress_bar
pad_text(text, width, "left"|"right"|"center")       # 按显示宽度补齐
center_text(screen, y, text, style)                  # 返回起始列
```

边框样式：`single` `double` `round` `heavy` `ascii` `none`。
`draw_sprite()` 会把空格当透明处理，方便叠在背景上。

### `Clock` —— 帧率

```python
clock = Clock(60, max_dt=0.25)   # 大卡顿后 dt 最多给 0.25 秒
dt = clock.tick()                # 等到下一帧边界，返回上一帧耗时
clock.sleep_for(0.1)             # 额外睡一会儿
```

采用"先 sleep 再短自旋"：大头交给内核，最后 2ms 自旋抹平 `sleep` 的粒度误差。
落后整帧时重置基准而不是疯狂追帧，所以掉帧之后不会突然快进。

---

## 内置演示

```bash
python -m escurses              # 玩一局贪吃蛇
python -m escurses --fps 20
python examples/02_colors.py    # 颜色总览
python examples/05_widgets.py   # 控件总览
```

---

## 架构

```
escurses/
├── terminal.py     Terminal：会话生命周期、尺寸变化、输入输出编排
├── screen.py       Screen：二维单元格缓冲区（纯内存，无 I/O）
├── render.py       行级 diff → 最小 ANSI 序列（纯函数）
├── input.py        KeyParser：CSI / SS3 / UTF-8 状态机
├── clock.py        Clock：固定步长节拍器
├── color.py        Style / Color / SGR / 色彩降级
├── textutil.py     显示宽度、字素簇、文本裁剪、控制字符消毒
├── widgets.py      边框、折行、精灵、进度条（纯函数）
├── _legacy.py      1.x 函数式 API 兼容层
├── demo.py         内置贪吃蛇
└── backends/
    ├── base.py     后端接口
    ├── ansi.py     POSIX：termios + os.read + select
    ├── windows.py  Windows：VT 开启 + msvcrt 扫描码翻译
    └── memory.py   内存后端（测试 / CI / 无终端降级）
```

分层的硬边界：**除 `backends/` 外，没有任何模块直接碰操作系统**。
所以缓冲区、渲染器、解析器、控件全部可以脱离终端单测 —— 这也是这个项目
能有 445 个测试的原因。

---

## 测试

```bash
pip install pytest
python -m pytest            # 445 passed, 3 skipped
```

测试构成：

| 层次 | 内容 |
|---|---|
| 单元测试 | 宽度计算、缓冲区、diff 渲染、SGR、按键状态机、时钟、控件 |
| **虚拟终端回放** | `tests/vt.py` 是一个迷你 ANSI 解释器：把库输出真的"画"一遍，再逐格对比缓冲区。排版错位、光标失控、样式漏复位全部会被抓到 |
| 随机化 fuzz | 25 组种子 × 12 轮随机涂改，每轮都回放校验 |
| 集成测试 | 无头跑完整局贪吃蛇 + 所有示例的绘制函数 |
| 性能回归 | 断言输出量级和"无改动帧零输出"，防止以后改慢 |
| 跨平台 | GitHub Actions 上 Ubuntu / Windows / macOS × Python 3.8 / 3.11 / 3.13 |

没有终端的环境（CI、SSH 到奇怪的容器）也能跑完整测试，因为它不需要真实 TTY。

---

## 修复清单

从 102 行原版到 2.0，改掉的实质问题：

| # | 原版行为 | 后果 | 2.0 做法 |
|---|---|---|---|
| 1 | 缓冲区宽度取 `屏幕宽度 - 1` | 最右一列永远画不了，画了直接 `IndexError` | 关闭自动换行（`CSI ?7l`），整宽可用 |
| 2 | 每帧对每格发一次 `ESC[y;xH` | 80×24 每帧 1920 次光标跳转 | 行级 diff + 连续输出，首帧 42KB → 5KB |
| 3 | `drawChar` 无边界检查 | 精灵出屏就崩 | 裁剪（`strict=True` 可还原为抛异常） |
| 4 | 不处理宽字符 | 中文/emoji 全部错位，边框被挤歪 | 按显示宽度排版 + 占位格，覆盖半格时自动拆字 |
| 5 | `sleepForFrame` 自旋条件写死 `< 0.01` | fps > 100 时反而被拖慢；100% 占一核 | 等到真实帧边界，先睡后短自旋 |
| 6 | `getch` 每次调用都 `tcsetattr` 两次 | 每帧 2 次系统调用；`TCSADRAIN` 会丢连按 | 只在 `open/close` 时切换一次终端模式 |
| 7 | POSIX 阻塞读从没进 cbreak | 行缓冲，必须回车才响应 | 进入 cbreak（保留 `ISIG`，Ctrl-C 仍可用） |
| 8 | `stdin.read(1)` 走文本缓冲层 | 方向键被拆成 `ESC`/`[`/`A` 三次事件 | `os.read` 读裸 fd + 状态机重组 |
| 9 | Windows 未处理 `\x00`/`\xe0` 前缀 | 方向键只收到半个事件 | 扫描码翻译成标准 ANSI，两平台共用解析器 |
| 10 | Windows 未开 VT | 老 conhost 上输出 `←[2J` 字面量 | `SetConsoleMode` 开启 `ENABLE_VIRTUAL_TERMINAL_PROCESSING` |
| 11 | `exitGame` 用 `subprocess.run("cls")` | 起子进程清屏；终端状态不还原 | 退出备用屏幕 + 还原光标/换行/模式，`atexit` 兜底 |
| 12 | 没有异常安全 | 崩溃后光标隐藏、终端变砖 | `with` / `try-finally` / `atexit` 三重保证 |
| 13 | 没有 alt-screen | 游戏内容污染用户滚动历史 | 进出 `CSI ?1049h/l` |
| 14 | 没有 resize 处理 | 拖窗口后花屏或越界崩溃 | 每帧检测尺寸，就地重建并保内容 |
| 15 | `clear()` 少了 `ESC[H` | 光标停在原处，后续绘制位置错乱 | 清屏 + 归位 |
| 16 | `cursorEcho` 不 flush | 光标状态可能延迟一帧才生效 | 立即 flush |
| 17 | 缓冲区写入不过滤控制字符 | 显示外部文本即可注入 ANSI 序列劫持终端 | `sanitize()` 统一替换为 `?` |
| 18 | 非 TTY 环境直接抛异常 | 管道/IDE 里跑不起来 | 后端降级 + 后台线程读输入 |
| 19 | 没有颜色 | 终端游戏只有黑白 | 16/256/真彩 + 自动降级 |
| 20 | 没有打包 | 只能复制文件 | `pyproject.toml` + 控制台入口 + `py.typed` |

---

## 从 1.x 迁移

**不需要改代码。** 只有三处行为变化，都是修复性质：

1. **最右一列现在能画了。** 如果你的代码依赖"画最后一列会抛 `IndexError`"来探测边界
   （不太可能），改用 `screen.width`。
2. **方向键等具名键返回字符串常量。** 以前按上键，Windows 上会依次收到 `"\x00"` 和 `"H"`，
   POSIX 上是 `"\x1b"`、`"["`、`"A"` —— 本来就没法用。现在返回 `"UP"`，
   可以和 `escurses.KEY_UP` 比较。
3. **`getTerminalSize()` 在非 TTY 环境返回 `(80, 24)` 而不是抛 `OSError`。**
   要判断环境请用 `linuxTerminalCheck()`。

另外 `exitGame()` 不再清屏 —— 它会退出备用屏幕，玩家能看回自己原来的终端内容。
想要旧效果就传 `exitGame(clear_after=True)`。

---

## 已知限制

诚实列在这里，免得你踩到：

- **鼠标事件未支持。** SGR 鼠标协议在 Windows conhost 上行为不一致，宁可不做也不做半成品。
- **字素簇分割是近似实现。** 覆盖了组合符、VS16、ZWJ 序列，但没有完整的
  Unicode 字素簇表（那需要 `regex` 依赖）。极少数复杂 emoji 序列宽度可能算错。
- **macOS 没有手动验证过。** CI 在 macOS 上跑全部测试（走的是 POSIX 后端），
  但换行与终端模式的实际表现我没在真机上确认。
- **Windows 需要 10 (1511+) 才支持 VT 序列。** 更老的系统会抛
  `TerminalNotSupportedError`，而不是输出乱码。
- **Ctrl+方向键在 Windows 上只覆盖四个方向键。** 其他组合拿不到键码。
- **帧率自旋的 2ms 尾巴**是拿 CPU 换精度，对笔记本电池不友好但游戏里通常无所谓；
  用 `Clock(fps, spin=False)` 可以关掉。

---

## 路线图

- [ ] 鼠标事件（先做 POSIX，Windows 单独开关）
- [ ] 双缓冲 + 真格级 diff（现在是行级段落 diff）
- [ ] `Sprite` / `Scene` 对象，给初学者更省心的抽象
- [ ] 完整 Unicode 字素簇（可选依赖）
- [ ] 录制/回放文件格式，方便做自动化演示

---

## 贡献

欢迎 PR，尤其是**测试**和**平台实测**。提 PR 之前请确保：

```bash
python -m pytest        # 全绿
python -m pyflakes escurses/
```

真的在 macOS 上跑过的话，告诉我结果 —— 那部分我确实缺第一手验证。

---

## 授权

本项目以 MIT 许可证发布。完整文本见 [LICENSE](./LICENSE)，来源与版权说明见
[NOTICE.md](./NOTICE.md)。上游已于 2026-11-04 添加 MIT 许可证；本 fork 已同步，
并保留原作者的版权声明。
