"""一个最小的 ANSI 虚拟终端，用来验证渲染输出。

这是测试基础设施里最要紧的一块：光断言"输出了某个转义序列"证明不了
玩家真能看到正确的画面。这里把库吐出的字节流**真的解释一遍**，还原成
一张字符网格，再和缓冲区对比 —— 只有这样，光标定位、宽字符占位、
样式重置、行尾残留这些坑才会被抓出来。
"""

from __future__ import annotations

import re
from typing import List, Tuple

from escurses.textutil import clusters

CSI = re.compile(r"\x1b\[([0-9;?]*)([@-~])")


class VirtualTerminal:
    """足够覆盖 EScurses 输出范围的 ANSI 解释器。"""

    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width = width
        self.height = height
        self.cx = 0
        self.cy = 0
        self.attr = "0"
        self.cursor_visible = True
        self.wrap = True
        self.pending_wrap = False
        self.alt_screen = False
        self.bell_count = 0
        self.titles: List[str] = []
        self.unknown_sequences: List[str] = []
        self.grid: List[List[str]] = self._blank_grid()
        self.attrs: List[List[str]] = [["0"] * width for _ in range(height)]

    # ---- 查询 ----------------------------------------------------------
    def _blank_grid(self) -> List[List[str]]:
        return [[" "] * self.width for _ in range(self.height)]

    def text(self) -> str:
        """返回可见内容（每行一条，按显示宽度对齐）。"""
        return "\n".join("".join(row) for row in self.grid)

    def line(self, y: int) -> str:
        return "".join(self.grid[y])

    def char_at(self, x: int, y: int) -> str:
        return self.grid[y][x]

    def attr_at(self, x: int, y: int) -> str:
        return self.attrs[y][x]

    # ---- 解释 ----------------------------------------------------------
    def feed(self, data: str) -> "VirtualTerminal":
        index = 0
        length = len(data)
        pending: List[str] = []
        while index < length:
            char = data[index]
            if char == "\x1b" or char in "\r\n\b\x07":
                self._flush(pending)
                if char == "\x1b":
                    index = self._escape(data, index)
                    continue
                if char == "\r":
                    self.cx = 0
                    self.pending_wrap = False
                elif char == "\n":
                    self._linefeed()
                    self.pending_wrap = False
                elif char == "\b":
                    self.cx = max(0, self.cx - 1)
                    self.pending_wrap = False
                else:
                    self.bell_count += 1
            elif char >= " ":
                pending.append(char)
            index += 1
        self._flush(pending)
        return self

    def _flush(self, pending: List[str]) -> None:
        """按显示单元（字素簇）落笔 —— 组合字符不能单独占一格。"""
        if not pending:
            return
        for chunk, width in clusters("".join(pending)):
            self._put_cluster(chunk, width)
        pending.clear()

    def _escape(self, data: str, index: int) -> int:
        if index + 1 >= len(data):
            return index + 1
        marker = data[index + 1]
        if marker == "[":
            match = CSI.match(data, index)
            if not match:
                self.unknown_sequences.append(data[index:index + 2])
                return index + 2
            self._csi(match.group(1), match.group(2))
            return match.end()
        if marker == "]":
            end = data.find("\x07", index)
            if end == -1:  # pragma: no cover
                end = data.find("\x1b\\", index)
                payload = data[index + 2:end]
            else:
                payload = data[index + 2:end]
            if ";" in payload:
                self.titles.append(payload.split(";", 1)[1])
            return end + 1
        if marker == "7":
            return index + 2
        if marker == "8":
            return index + 2
        self.unknown_sequences.append(data[index:index + 2])
        return index + 2

    def _csi(self, params: str, final: str) -> None:
        private = params.startswith("?")
        body = params[1:] if private else params
        numbers = [int(p) if p.isdigit() else 0 for p in body.split(";")] if body else []

        if private:
            value = numbers[0] if numbers else 0
            if final == "h":
                if value == 25:
                    self.cursor_visible = True
                elif value == 7:
                    self.wrap = True
                elif value == 1049:
                    self.alt_screen = True
                    self.grid = self._blank_grid()
                    self.attrs = [["0"] * self.width for _ in range(self.height)]
                    self.cx = self.cy = 0
            elif final == "l":
                if value == 25:
                    self.cursor_visible = False
                elif value == 7:
                    self.wrap = False
                elif value == 1049:
                    self.alt_screen = False
            else:  # pragma: no cover
                self.unknown_sequences.append(params + final)
            return

        if final in ("H", "f"):
            row = numbers[0] if len(numbers) > 0 and numbers[0] else 1
            column = numbers[1] if len(numbers) > 1 and numbers[1] else 1
            self.cy = min(self.height - 1, max(0, row - 1))
            self.cx = min(self.width - 1, max(0, column - 1))
            self.pending_wrap = False
            return
        if final == "J":
            mode = numbers[0] if numbers else 0
            if mode == 2:
                self.grid = self._blank_grid()
                self.attrs = [["0"] * self.width for _ in range(self.height)]
        elif final == "K":
            for x in range(self.cx, self.width):
                self.grid[self.cy][x] = " "
                self.attrs[self.cy][x] = "0"
        elif final == "m":
            self.attr = params or "0"
        elif final in ("A", "B", "C", "D"):  # pragma: no cover - EScurses 不产生
            self.unknown_sequences.append(params + final)
        else:
            self.unknown_sequences.append(params + final)

    def _linefeed(self) -> None:
        self.cy += 1
        if self.cy >= self.height:
            self.grid.pop(0)
            self.attrs.pop(0)
            self.grid.append([" "] * self.width)
            self.attrs.append(["0"] * self.width)
            self.cy = self.height - 1

    def _put_cluster(self, chunk: str, width: int) -> None:
        width = width or 1

        # 真实终端是"延迟换行"：写满最后一列时光标停在原地，
        # 下一个字符才换行。立刻换行会导致最后一列整整少画一行。
        if self.pending_wrap:
            self.pending_wrap = False
            self.cx = 0
            self._linefeed()

        if self.cx + width > self.width:
            if not self.wrap:
                return
            self.cx = 0
            self._linefeed()

        self.grid[self.cy][self.cx] = chunk
        self.attrs[self.cy][self.cx] = self.attr
        if width == 2 and self.cx + 1 < self.width:
            self.grid[self.cy][self.cx + 1] = ""
            self.attrs[self.cy][self.cx + 1] = self.attr

        self.cx += width
        if self.cx >= self.width:
            self.cx = self.width - 1
            self.pending_wrap = self.wrap

    # ---- 与缓冲区对比 --------------------------------------------------
    def mismatches(self, screen) -> List[Tuple[int, str, str]]:
        """返回与 ``Screen`` 不一致的行：``[(行号, 期望, 实际), ...]``。"""
        problems = []
        for y in range(min(self.height, screen.height)):
            expected = "".join(cell[0] for cell in screen.row(y))
            actual = "".join(self.grid[y])
            if expected != actual:
                problems.append((y, expected, actual))
        return problems
