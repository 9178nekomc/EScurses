# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.0.0] — 2026-11-01

内部实现重写，**公开 API 完全向后兼容**。原始版本 102 行，本次改动覆盖渲染、
输入、平台后端、时钟、颜色、控件、打包与测试。

### 新增

- **对象式 API**：`Terminal` / `Screen` / `Style` / `Color` / `Clock` / `widgets`，
  旧函数式 API 全部保留。
- **后端抽象层**：`AnsiBackend`（POSIX）、`WindowsBackend`（Windows）、
  `MemoryBackend`（无头测试与降级）。
- **颜色系统**：16 / 256 / 24 位三档，能力探测 + 自动量化降级；
  `Color.named/index/rgb/parse`，`Style` 不可变且可 `replace()`。
- **控件库**：`draw_box`（6 种边框 + 标题）、`draw_paragraph`/`wrap_text`（中英文混排折行）、
  `draw_sprite`（空格透明）、`draw_progress_bar`、`pad_text`（按显示宽度补齐）、
  `center_text`、`draw_hline`/`draw_vline`。
- **完整的按键解析**：CSI / SS3 / UTF-8 状态机，支持方向键、Home/End/PgUp/PgDn、
  F1-F12、Shift/Ctrl/Alt 修饰符、孤立 Esc 超时判定、跨 `read` 边界的分包。
- **备用屏幕**（`CSI ?1049h/l`）：游戏不再污染用户的滚动历史。
- **窗口缩放自适应**：每帧检测尺寸，就地重建缓冲区并保留重叠内容。
- **`Clock` 固定步长节拍器**：`max_dt` 截断、落后重置、可选自旋。
- **内置贪吃蛇 Demo**（`python -m escurses`）。
- **打包**：`pyproject.toml`、`py.typed`、`escurses` 控制台入口、CI 矩阵。
- **445 个测试**：含虚拟终端回放、随机化 fuzz、集成与性能回归。

### 修复

- 缓冲区宽度少 1 列，最右一列无法绘制且会 `IndexError`。
- 每格一次绝对定位导致的高开销渲染（首帧输出量 42 KB → 5 KB）。
- `sleepForFrame` 自旋条件错误：fps > 100 时反而被拖慢，且无条件忙等占满一核。
- POSIX `getch` 每次调用都切换终端模式（每帧 2 次系统调用，且会丢连按）。
- POSIX 阻塞读取从未进入 cbreak，必须按回车才有响应。
- POSIX 使用文本层 `read(1)`，方向键序列与多字节 UTF-8 被拆碎。
- Windows 未处理 `\x00`/`\xe0` 扫描码前缀，方向键只收到半个事件。
- Windows 未开启 `ENABLE_VIRTUAL_TERMINAL_PROCESSING`，老 conhost 上输出乱码。
- `exitGame` 用 `subprocess.run("cls", shell=True)` 清屏，且不还原终端状态。
- 无异常安全：崩溃后光标隐藏、终端模式残留。
- 宽字符（中文/emoji）未按显示宽度排版，导致整体错位；覆盖半个宽字符时留下孤儿。
- `fill()` 在右边界会写入"只有前半截"的宽字符，造成缓冲区与终端列错位。
- 缓冲区不过滤控制字符，显示外部文本可注入 ANSI 序列。
- `clear()` 缺少光标归位；`cursorEcho` 缺少 flush。
- 非 TTY 环境直接抛 `OSError`，无法在管道/IDE 中运行。
- Windows 端 ctypes 未声明 `restype` / `argtypes`：`HANDLE` 在 64 位下被当成 32 位
  `int` 截断，导致 `GetConsoleMode` 与 `GetConsoleScreenBufferInfo` 静默失败，
  真实的控制台被误判为"不支持"，窗口尺寸永远退回 80×24。
- Windows 端读取 stdin 的后台线程阻塞在 `sys.stdin.buffer.read`，
  持有 `BufferedReader` 锁，解释器退出时触发
  `Fatal Python error: _enter_buffered_busy`（退出码 139）。改为裸 fd 的 `os.read`。

### 行为变更（均为修复性质，详见 README）

1. 最右一列现在可以绘制。
2. 方向键等具名键由 `getch()` 返回字符串常量（如 `"UP"`），不再返回半个转义序列。
3. `getTerminalSize()` 在非 TTY 环境返回 `(80, 24)` 而非抛异常。
4. `exitGame()` 不再清屏（改为退出备用屏幕），可传 `clear_after=True` 恢复旧行为。

### 移除

- 单文件 `escurses.py`（已由 `escurses/` 包取代）。复制文件夹同样可以"下载即用"。

## [1.0.0] — 初始版本

- 102 行单文件：`initGame` / `clear` / `drawChar` / `refresh` / `getch` /
  `cursorEcho` / `exitGame` / `frameStart` / `sleepForFrame` /
  `getTerminalSize` / `linuxTerminalCheck`。
