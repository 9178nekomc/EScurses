"""显示宽度计算与文本裁剪。

终端里并不是"一个字符占一列"：

* CJK 汉字、假名、全角符号、绝大多数 emoji 占 **2 列**（东亚宽度 W/F）；
* 组合附加符号、变体选择符、零宽连接符占 **0 列**；
* 其余可打印字符占 1 列。

缓冲区排版必须按 *显示宽度* 而不是 ``len(str)`` 计算，否则中文和 emoji
会把手画的边框全部挤歪 —— 这是绝大多数简易终端库的通病。
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import List, Tuple

__all__ = [
    "char_width",
    "text_width",
    "clusters",
    "truncate",
    "sanitize",
    "DEFAULT_SUBSTITUTE",
]

#: 遇到控制字符时替换成什么。终端库绝不能把 ``\\x1b`` 原样写进输出流，
#: 否则游戏里显示的任何外部文本都能注入 ANSI 转义序列劫持终端
#: （清屏、改标题、甚至在部分终端里读写剪贴板）。
DEFAULT_SUBSTITUTE = "?"

_ZWJ = "\u200d"
_VS16 = "\ufe0f"
_CONTROL_CATEGORIES = frozenset(("Cc", "Cs", "Zl", "Zp"))


@lru_cache(maxsize=4096)
def char_width(ch: str) -> int:
    """返回单个字符的显示宽度（0、1 或 2）。

    控制字符返回 0 —— 它们根本不该被画到缓冲区里，由 :func:`sanitize`
    负责替换。
    """
    if not ch:
        return 0
    category = unicodedata.category(ch)
    if category in _CONTROL_CATEGORIES:
        return 0
    if category in ("Mn", "Me", "Cf"):
        # 组合记号 / 变体选择符 / 零宽字符
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def clusters(text: str) -> List[Tuple[str, int]]:
    """把字符串切成显示单元列表 ``[(文本, 宽度), ...]``。

    这里不做完整的 Unicode 字素簇分割（那需要 ``regex`` 第三方库），
    但覆盖了终端游戏实际会遇到的三种情况：

    1. 普通字符 → 宽度 1；
    2. 组合序列（如 ``e`` + U+0301）→ 合成一个单元，宽度 1；
    3. ZWJ/VS16 序列（如 👨‍👩‍👧、❤️）→ 合成一个单元，宽度 2。

    算法分两遍：第一遍按"基础字符 + 其后所有零宽字符"切段，
    第二遍把以 ZWJ 结尾的段与下一段合并。
    """
    if not text:
        return []

    # 第一遍：基础字符 + 尾随零宽字符
    base: List[Tuple[str, int]] = []
    pending = ""
    pending_width = 0
    for ch in text:
        width = char_width(ch)
        if width == 0:
            if pending:
                pending += ch
            continue  # 首部零宽字符无处附着，直接丢弃
        if pending:
            base.append((pending, pending_width))
        pending = ch
        pending_width = width
    if pending:
        base.append((pending, pending_width))

    # 第二遍：合并 ZWJ 序列 —— 前一段以 ZWJ 结尾说明它还没画完
    merged: List[Tuple[str, int]] = []
    for chunk, width in base:
        if merged and merged[-1][0].endswith(_ZWJ):
            prev_text, prev_width = merged[-1]
            merged[-1] = (prev_text + chunk, max(prev_width, width))
        else:
            merged.append((chunk, width))

    # VS16 强制 emoji 呈现，终端按两列显示（❤️ 是 2 列而不是 1 列）
    return [
        (chunk, 2 if _VS16 in chunk else width) for chunk, width in merged
    ]


def text_width(text: str) -> int:
    """返回整个字符串的显示宽度（列数）。"""
    if not text:
        return 0
    if len(text) == 1:
        return char_width(text)
    return sum(width for _t, width in clusters(text))


def truncate(text: str, width: int) -> str:
    """把文本裁剪到不超过 ``width`` 列，不会切断宽字符。"""
    if width <= 0:
        return ""
    used = 0
    kept = []
    for chunk, chunk_width in clusters(text):
        if used + chunk_width > width:
            break
        kept.append(chunk)
        used += chunk_width
    return "".join(kept)


def sanitize(text: str, substitute: str = DEFAULT_SUBSTITUTE) -> str:
    """把控制字符替换成安全字符，防止 ANSI 注入。

    ``\\n`` / ``\\t`` 也一并替换 —— 缓冲区是二维网格，换行没有意义，
    需要多行请用 :func:`escurses.widgets.draw_text`。
    """
    if not text:
        return text
    out = []
    for ch in text:
        if unicodedata.category(ch) in _CONTROL_CATEGORIES:
            out.append(substitute)
        else:
            out.append(ch)
    return "".join(out)
