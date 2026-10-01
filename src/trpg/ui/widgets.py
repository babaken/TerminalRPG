"""ウィンドウ部品：会話（メッセージ）窓・選択肢窓・パネル描画の補助。"""
from __future__ import annotations

from typing import Optional

from ..term import Buffer, Rect, Style, text_width, wrap
from ..term.buffer import BOX_SINGLE
from . import markup
from .markup import Glyph

FRAME = Style.of("white")
TEXT = Style.of("bright_white")
DIM_TEXT = Style.of("gray")
CURSOR = Style.of("bright_yellow", bold=True)


class MessageWindow:
    """会話窓。行を折り返してページ分けし、1 文字ずつ表示する。

    本文の制御コード（\\w 待ち・\\c[色]・\\s 速さ。ui/markup.py）に従う。
    ``pages`` は表示文字列（制御コードを除いたもの）、``_glyphs`` は 1 文字ずつの情報。
    """

    CHARS_PER_SEC = 40

    def __init__(self):
        self.pages: list[list[str]] = []
        self._glyphs: list[list[list[Glyph]]] = []
        self.page = 0
        self.shown = 0.0          # 現在ページで表示済みの文字数
        self._budget = 0.0        # 文字送りに使える残り時間
        self.speaker = ""
        self._width = 0
        self._rows = 0
        self._lines: list[tuple[str, str]] = []
        self.blink = 0.0

    @property
    def active(self) -> bool:
        return bool(self.pages)

    def open(self, lines: list[tuple[str, str]]) -> None:
        self._lines = lines
        self.speaker = next((sp for sp, _ in lines if sp), "")
        self._paginate()
        self.page = 0
        self.shown = 0.0
        self._budget = 0.0

    def close(self) -> None:
        self.pages = []
        self._glyphs = []
        self._lines = []

    def _paginate(self) -> None:
        rows: list[list[Glyph]] = []
        for _, text in self._lines:
            rows.extend(markup.wrap(markup.parse(text), max(1, self._width or 90)))
        per = max(1, self._rows or 3)
        self._glyphs = [rows[i:i + per] for i in range(0, len(rows), per)] or [[[]]]
        self.pages = [["".join(g.ch for g in row) for row in page] for page in self._glyphs]

    def layout(self, width: int, rows: int) -> None:
        """表示領域の大きさが変わったら折り返し直す。"""
        if (width, rows) != (self._width, self._rows):
            self._width, self._rows = width, rows
            if self._lines:
                page_start = sum(len(p) for p in self.pages[: self.page])
                self._paginate()
                # だいたい同じ位置のページに戻す
                acc = 0
                for i, p in enumerate(self.pages):
                    if acc + len(p) > page_start:
                        self.page = i
                        break
                    acc += len(p)

    def _page_glyphs(self) -> list[Glyph]:
        if not self._glyphs:
            return []
        return [g for row in self._glyphs[self.page] for g in row]

    def _page_len(self) -> int:
        return len(self._page_glyphs())

    @property
    def page_done(self) -> bool:
        return self.shown >= self._page_len()

    @property
    def last_page(self) -> bool:
        return self.page >= len(self.pages) - 1

    def update(self, dt: float) -> None:
        self.blink += dt
        glyphs = self._page_glyphs()
        if self.shown >= len(glyphs):
            self._budget = 0.0
            return
        self._budget += dt
        while self.shown < len(glyphs):
            g = glyphs[int(self.shown)]
            cost = g.wait + (0.0 if g.speed <= 0 else 1.0 / (self.CHARS_PER_SEC * g.speed))
            if self._budget < cost:
                break
            self._budget -= cost
            self.shown = int(self.shown) + 1

    def advance(self) -> bool:
        """決定キー。表示途中なら全部出す。ページ末なら次へ。全部読み終えたら True。"""
        if not self.page_done:
            self.shown = self._page_len()
            return False
        if self.last_page:
            return True
        self.page += 1
        self.shown = 0.0
        self._budget = 0.0
        return False

    def draw(self, buf: Buffer, rect: Rect, show_cursor: bool = True) -> None:
        inner = buf.box(rect, FRAME, chars=BOX_SINGLE)
        self.layout(inner.w - 2, inner.h)
        if not self.pages:
            return
        left = int(self.shown)
        for i, row in enumerate(self._glyphs[self.page]):
            if left <= 0:
                break
            x = inner.x + 1
            for g in row[:left]:
                if g.ch:
                    st = TEXT if not g.color else _color_style(g.color)
                    x = buf.put(x, inner.y + i, g.ch, st, clip=inner)
            left -= len(row)
        if show_cursor and self.page_done and int(self.blink * 3) % 2 == 0:
            mark = "▼" if not self.last_page else "▽"
            buf.put(inner.right - 2, inner.bottom - 1, mark, CURSOR, clip=inner)


def _color_style(name: str) -> Style:
    try:
        return Style.of(name, bold=True)
    except ValueError:
        return TEXT


class ChoiceWindow:
    def __init__(self, options: list[str], cancel_index: Optional[int] = None):
        self.options = options
        self.index = 0
        self.cancel_index = cancel_index

    def move(self, d: int) -> None:
        self.index = (self.index + d) % len(self.options)

    def size(self) -> tuple[int, int]:
        w = max(text_width(o) for o in self.options) + 6
        return w, len(self.options) + 2

    def draw(self, buf: Buffer, right: int, bottom: int) -> None:
        w, h = self.size()
        w = min(w, buf.width)
        rect = Rect(max(0, right - w), max(0, bottom - h), w, h)
        inner = buf.box(rect, FRAME, chars=BOX_SINGLE)
        for i, opt in enumerate(self.options):
            sel = i == self.index
            buf.put(inner.x + 1, inner.y + i, ("▶ " if sel else "  ") + opt,
                    CURSOR if sel else TEXT, clip=inner)


def gauge_text(cur: int, mx: int) -> str:
    return f"{cur:>3}/{mx:>3}"
