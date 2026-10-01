"""セルバッファ。画面 1 枚分の文字とスタイルを保持する。

- 1 セル = (文字, Style)。
- 全角文字は 2 セルを占め、右側のセルには継続マーカー ``CONT`` を置く。
- 全角文字の片側だけを上書きした場合、残った片側は空白に置き換えて整合性を保つ。
"""
from __future__ import annotations

from typing import Iterable, NamedTuple, Optional

from .style import DEFAULT, Style
from .width import char_width, text_width

CONT = ""  # 全角文字の右半分（継続セル）

Cell = tuple  # (str, Style)


class Rect(NamedTuple):
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def inset(self, dx: int, dy: int | None = None) -> "Rect":
        dy = dx if dy is None else dy
        return Rect(self.x + dx, self.y + dy, max(0, self.w - 2 * dx), max(0, self.h - 2 * dy))

    def intersect(self, other: "Rect") -> "Rect":
        x0, y0 = max(self.x, other.x), max(self.y, other.y)
        x1, y1 = min(self.right, other.right), min(self.bottom, other.bottom)
        return Rect(x0, y0, max(0, x1 - x0), max(0, y1 - y0))


BOX_SINGLE = "┌┐└┘─│"
BOX_DOUBLE = "╔╗╚╝═║"
BOX_ASCII = "++++-|"


class Buffer:
    def __init__(self, width: int, height: int, fill_style: Style = DEFAULT):
        self.width = width
        self.height = height
        self.rows: list[list[Cell]] = [[(" ", fill_style)] * width for _ in range(height)]
        # 端末のカーソルを表示する位置（文字入力中のみ）。IME の変換中文字列はここに表示される
        self.cursor: Optional[tuple[int, int]] = None

    # ------------------------------------------------------------------ 基本
    @property
    def rect(self) -> Rect:
        return Rect(0, 0, self.width, self.height)

    def clear(self, style: Style = DEFAULT) -> None:
        blank = (" ", style)
        for y in range(self.height):
            self.rows[y] = [blank] * self.width
        self.cursor = None

    def copy(self) -> "Buffer":
        b = Buffer.__new__(Buffer)
        b.width, b.height = self.width, self.height
        b.rows = [row[:] for row in self.rows]
        b.cursor = self.cursor
        return b

    def get(self, x: int, y: int) -> Cell:
        return self.rows[y][x]

    def row_text(self, y: int) -> str:
        """テスト・デバッグ用：1 行を文字列で返す。"""
        return "".join(c[0] for c in self.rows[y])

    def _set(self, x: int, y: int, ch: str, style: Style, w: int) -> None:
        row = self.rows[y]
        width = self.width
        # 継続セルに書く → 左の全角文字が壊れるので空白化
        if row[x][0] == CONT and x > 0:
            row[x - 1] = (" ", row[x - 1][1])
        end = x + w  # 書き込み範囲の次
        # 書き込み範囲の直後が継続セル → その全角文字の左半分を上書きしたので空白化
        if end < width and row[end][0] == CONT:
            row[end] = (" ", row[end][1])
        row[x] = (ch, style)
        if w == 2:
            row[x + 1] = (CONT, style)

    # ------------------------------------------------------------------ 描画
    def put(self, x: int, y: int, text: str, style: Style = DEFAULT,
            clip: Optional[Rect] = None) -> int:
        """(x, y) から 1 行の文字列を書く。``clip`` 外ははみ出さない。書き終えた次の x を返す。"""
        c = self.rect if clip is None else clip.intersect(self.rect)
        if not (c.y <= y < c.bottom):
            return x + text_width(text)
        left, right = c.x, c.right
        last_x = -1
        for ch in text:
            if ch == "\t":
                ch = " "
            w = char_width(ch)
            if w == 0:
                # 結合文字は直前のセルに連結
                if ch >= " " and last_x >= 0:
                    pc, ps = self.rows[y][last_x]
                    self.rows[y][last_x] = (pc + ch, ps)
                continue
            if x >= right:
                x += w
                continue
            if x < left:
                if w == 2 and x + 1 == left:
                    self._set(left, y, " ", style, 1)
                x += w
                continue
            if x + w > right:
                # 全角の左半分だけ入る → 空白で埋める
                self._set(x, y, " ", style, 1)
                x += w
                continue
            self._set(x, y, ch, style, w)
            last_x = x
            x += w
        return x

    def put_center(self, y: int, text: str, style: Style = DEFAULT, clip: Optional[Rect] = None) -> None:
        c = self.rect if clip is None else clip
        x = c.x + (c.w - text_width(text)) // 2
        self.put(x, y, text, style, clip=c)

    def put_lines(self, x: int, y: int, lines: Iterable[str], style: Style = DEFAULT,
                  clip: Optional[Rect] = None, transparent: bool = False) -> None:
        """複数行（AA など）を書く。``transparent`` なら半角空白を描かない。"""
        for i, line in enumerate(lines):
            if not transparent:
                self.put(x, y + i, line, style, clip)
                continue
            cx = x
            run_start, run = cx, []
            for ch in line:
                w = char_width(ch)
                if ch == " ":
                    if run:
                        self.put(run_start, y + i, "".join(run), style, clip)
                        run = []
                    cx += 1
                    run_start = cx
                    continue
                if not run:
                    run_start = cx
                run.append(ch)
                cx += w
            if run:
                self.put(run_start, y + i, "".join(run), style, clip)

    def fill(self, rect: Rect, ch: str = " ", style: Style = DEFAULT) -> None:
        r = rect.intersect(self.rect)
        w = char_width(ch)
        if w != 1:
            # 全角文字での塗りつぶしは put に任せる
            line = ch * (r.w // max(w, 1))
            for y in range(r.y, r.bottom):
                self.put(r.x, y, line, style, clip=r)
            return
        for y in range(r.y, r.bottom):
            row = self.rows[y]
            if r.x > 0 and row[r.x][0] == CONT:
                row[r.x - 1] = (" ", row[r.x - 1][1])
            if r.right < self.width and row[r.right][0] == CONT:
                row[r.right] = (" ", row[r.right][1])
            row[r.x:r.right] = [(ch, style)] * r.w

    def box(self, rect: Rect, style: Style = DEFAULT, title: str = "", chars: str = BOX_SINGLE,
            fill: bool = True, title_style: Optional[Style] = None) -> Rect:
        """枠を描き、内側の Rect を返す。"""
        x, y, w, h = rect
        if w < 2 or h < 2:
            return Rect(x, y, 0, 0)
        tl, tr, bl, br, hz, vt = chars
        if fill:
            self.fill(Rect(x + 1, y + 1, w - 2, h - 2), " ", style)
        self.put(x, y, tl + hz * (w - 2) + tr, style)
        self.put(x, y + h - 1, bl + hz * (w - 2) + br, style)
        for yy in range(y + 1, y + h - 1):
            self.put(x, yy, vt, style)
            self.put(x + w - 1, yy, vt, style)
        if title and w > 4:
            self.put(x + 2, y, " " + title + " ", title_style or style, clip=Rect(x + 1, y, w - 2, 1))
        return Rect(x + 1, y + 1, w - 2, h - 2)

    def blit(self, src: "Buffer", x: int, y: int) -> None:
        """別バッファを重ねる。"""
        for sy in range(src.height):
            dy = y + sy
            if not 0 <= dy < self.height:
                continue
            for sx, (ch, st) in enumerate(src.rows[sy]):
                dx = x + sx
                if ch == CONT or not 0 <= dx < self.width:
                    continue
                w = char_width(ch[0]) if ch else 1
                if dx + w > self.width:
                    continue
                self._set(dx, dy, ch, st, w)

    def map_styles(self, fn) -> None:
        """全セルのスタイルを変換する（tint などの画面効果用）。"""
        cache: dict = {}
        for row in self.rows:
            for i, (ch, st) in enumerate(row):
                ns = cache.get(st)
                if ns is None:
                    ns = cache[st] = fn(st)
                row[i] = (ch, ns)
