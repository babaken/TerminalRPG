"""アスキーアート（AA）の描画。色ファイル（.color）に対応する（基本設計 12 章）。

色ファイルは AA と同じ名前で拡張子だけ .color（aa/slime.txt → aa/slime.color）。
AA と同じ行・同じ文字の位置に 1 文字ずつ色コードを書く：
    k r g y b m c w   … 黒 赤 緑 黄 青 紫 水 白
    K R G Y B M C W   … 明るい色
    . か空白          … 既定の色（描くときに指定した色）
行や文字が足りない部分は既定の色になる。
"""
from __future__ import annotations

from typing import Optional

from ..term import Buffer, Rect, Style
from ..term.style import COLOR_CODES
from ..term.width import char_width

DEFAULT_CODES = (".", " ")
VALID_CODES = set(COLOR_CODES) | set(DEFAULT_CODES)


def color_path(aa_path: str) -> str:
    return aa_path[:-4] + ".color" if aa_path.endswith(".txt") else aa_path + ".color"


def draw_aa(buf: Buffer, x: int, y: int, lines: list[str], base: Style,
            colors: Optional[list[str]] = None, clip: Optional[Rect] = None, transparent: bool = True) -> None:
    """AA を描く。colors があれば 1 文字ずつ色を付ける。transparent なら半角空白は描かない（下が透ける）。"""
    if not colors:
        buf.put_lines(x, y, lines, base, clip=clip, transparent=transparent)
        return
    for i, line in enumerate(lines):
        crow = colors[i] if i < len(colors) else ""
        cx = x
        for j, ch in enumerate(line):
            w = char_width(ch)
            if ch == " " and transparent:
                cx += 1
                continue
            code = crow[j] if j < len(crow) else "."
            st = base if code in DEFAULT_CODES or code not in COLOR_CODES else base._replace(fg=COLOR_CODES[code])
            buf.put(cx, y + i, ch, st, clip=clip)
            cx += w
