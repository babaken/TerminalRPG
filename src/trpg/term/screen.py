"""ダブルバッファ画面。

``back`` に描いて ``present()`` すると、前回出力した ``front`` との差分だけを ANSI で出力する。
端末サイズが変わったら両バッファを作り直し、次の present で全面再描画する。
"""
from __future__ import annotations

import shutil
import sys
from typing import Callable, Optional, TextIO

from .buffer import CONT, Buffer
from .style import DEFAULT, sgr

SizeFn = Callable[[], tuple[int, int]]

# 端末制御シーケンス
ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"
CURSOR_HIDE = "\x1b[?25l"
CURSOR_SHOW = "\x1b[?25h"
AUTOWRAP_OFF = "\x1b[?7l"   # 右下セルへの書き込みでスクロールしないように
AUTOWRAP_ON = "\x1b[?7h"
CLEAR = "\x1b[2J"
RESET = "\x1b[0m"


def terminal_size() -> tuple[int, int]:
    s = shutil.get_terminal_size(fallback=(100, 30))
    return s.columns, s.lines


class Screen:
    def __init__(self, out: Optional[TextIO] = None, size_fn: SizeFn = terminal_size,
                 use_color: bool = True):
        self.out = out if out is not None else sys.stdout
        self.size_fn = size_fn
        self.use_color = use_color
        w, h = self._read_size()
        self.back = Buffer(w, h)
        self.front: Optional[Buffer] = None  # None = 次回は全面再描画
        self.bytes_written = 0  # 直近 present の出力文字数（デバッグ表示用）
        self._cursor_shown: Optional[tuple[int, int]] = None  # 前回表示したカーソル位置

    def _read_size(self) -> tuple[int, int]:
        w, h = self.size_fn()
        return max(1, w), max(1, h)

    @property
    def width(self) -> int:
        return self.back.width

    @property
    def height(self) -> int:
        return self.back.height

    # ---------------------------------------------------------------- 開始・終了
    def start(self) -> None:
        self._write(ALT_SCREEN_ON + CURSOR_HIDE + AUTOWRAP_OFF + RESET + CLEAR)
        self.front = None

    def stop(self) -> None:
        self._write(RESET + AUTOWRAP_ON + CURSOR_SHOW + ALT_SCREEN_OFF)

    def _write(self, s: str) -> None:
        self.out.write(s)
        self.out.flush()

    # ---------------------------------------------------------------- サイズ
    def check_resize(self) -> bool:
        """端末サイズが変わっていればバッファを作り直して True を返す。"""
        w, h = self._read_size()
        if (w, h) == (self.back.width, self.back.height):
            return False
        self.back = Buffer(w, h)
        self.front = None
        return True

    def invalidate(self) -> None:
        """次回 present で全面再描画させる（画面が乱れたとき用）。"""
        self.front = None

    # ---------------------------------------------------------------- 出力
    def present(self) -> None:
        data = self.render_diff()
        cur = self.back.cursor
        if cur is not None:
            x = min(max(cur[0], 0), self.back.width - 1)
            y = min(max(cur[1], 0), self.back.height - 1)
            cur = (x, y)
        if data or cur != self._cursor_shown:
            if cur is not None:
                # 描画で動いたカーソルを入力位置へ戻して表示（IME の変換文字列がここに出る）
                data += f"\x1b[{cur[1] + 1};{cur[0] + 1}H" + CURSOR_SHOW
            elif self._cursor_shown is not None:
                data += CURSOR_HIDE
            self._cursor_shown = cur
        self.bytes_written = len(data)
        if data:
            self._write(data)
        self.front = self.back.copy()

    def render_diff(self) -> str:
        back = self.back
        front = self.front
        full = front is None or front.width != back.width or front.height != back.height
        parts: list[str] = []
        if full:
            parts.append(RESET + CURSOR_HIDE + CLEAR)
            self._cursor_shown = None
        width = back.width
        cur_style = None
        for y in range(back.height):
            brow = back.rows[y]
            frow = None if full else front.rows[y]
            if frow is not None and frow == brow:
                continue
            x = 0
            cursor_x = -1
            while x < width:
                cell = brow[x]
                if frow is not None and frow[x] == cell:
                    x += 1
                    continue
                if cell[0] == CONT and x > 0 and brow[x - 1][0] != CONT:
                    # 全角の右半分だけ変わった → 左半分から書き直す
                    x -= 1
                    cell = brow[x]
                if cursor_x != x:
                    parts.append(f"\x1b[{y + 1};{x + 1}H")
                if cell[1] != cur_style:
                    cur_style = cell[1]
                    parts.append(sgr(cur_style, self.use_color))
                ch = cell[0]
                if ch == CONT:  # 孤立した継続セル（通常起きない）
                    ch = " "
                    adv = 1
                elif x + 1 < width and brow[x + 1][0] == CONT:
                    adv = 2
                else:
                    adv = 1
                parts.append(ch)
                x += adv
                cursor_x = x
        if parts and cur_style != DEFAULT:
            parts.append(RESET)
        return "".join(parts)
