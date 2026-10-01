"""マップエディタの入力フォーム：NPC・ワープ・イベントの項目を編集する（3-3b）。

項目の種類：
    str     文字列（Enter で入力。空なら書かない）
    int     0 以上の整数
    list    道順（空白か , で区切る）
    choice  選択肢（Enter / ← → で切り替え）
    bool    はい / いいえ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..data.models import EVENT_TRIGGERS, NPC_MOVES, ROUTE_STEPS
from ..data.reader import ID_RE
from ..term import Buffer, Key, KeyEvent, Rect, Style, text_width, truncate
from ..term.style import COLORS

KIND_NAMES = {"npc": "NPC", "warp": "ワープ", "event": "イベント"}
COLOR_NAMES = [""] + [c for c in COLORS if c != "grey"]
DIRS = ["", "up", "down", "left", "right"]

TEXT = Style()
DIM = Style.of("gray")
LABEL = Style.of("bright_cyan")
HILITE = Style.of("black", "bright_yellow")
EDIT = Style.of("bright_white", underline=True)
ERR = Style.of("bright_red")


@dataclass
class Field:
    key: str
    label: str
    type: str = "str"
    choices: list = field(default_factory=list)
    required: bool = False
    default: Any = ""                 # この値なら（もともと書いていなければ）書かない


def fields_for(kind: str, map_ids: list[str]) -> list[Field]:
    if kind == "npc":
        return [Field("id", "ID", required=True), Field("glyph", "文字（幅 2）", required=True),
                Field("color", "色", "choice", COLOR_NAMES), Field("move", "動き", "choice", list(NPC_MOVES), default="fixed"),
                Field("route", "道順", "list", default=[]), Field("talk", "話しかけたとき（ラベル）"),
                Field("when", "出現する条件")]
    if kind == "warp":
        return [Field("to", "行き先のマップ", "choice", list(map_ids), required=True),
                Field("tx", "行き先 x", "int", default=None), Field("ty", "行き先 y", "int", default=None),
                Field("dir", "移動後の向き", "choice", DIRS)]
    return [Field("label", "ラベル", required=True),
            Field("trigger", "きっかけ", "choice", list(EVENT_TRIGGERS), default="check"),
            Field("once", "一度きり", "bool", default=False), Field("when", "条件")]


# 新しく作るときの項目の順（Map.data の書き方に合わせる）
ORDER = {
    "npc": ["id", "glyph", "color", "x", "y", "move", "route", "talk", "when"],
    "warp": ["x", "y", "to", "tx", "ty", "dir"],
    "event": ["x", "y", "trigger", "label", "once", "when"],
}


def show(f: Field, v: Any) -> str:
    if f.type == "list":
        return " ".join(v or [])
    if f.type == "bool":
        return "はい" if v else "いいえ"
    if v is None or v == "":
        return "（なし）" if f.type != "int" else ""
    return str(v)


class ObjectForm:
    """1 つの NPC・ワープ・イベントの編集。submit が成功したら done になる。"""

    def __init__(self, kind: str, values: dict, map_ids: list[str], *, index: Optional[int] = None,
                 validate: Optional[Callable[["ObjectForm", dict], str]] = None):
        self.kind = kind
        self.index = index                       # 既存の何番目か（新規は None）
        self.original = dict(values)
        self.fields = fields_for(kind, map_ids)
        self.values = {f.key: values.get(f.key, f.default) for f in self.fields}
        self.validate = validate
        self.row = 0
        self.editing = False
        self.buffer = ""
        self.error = ""
        self.result: Optional[dict] = None       # 書き込む項目（None は消す）
        self.closed = False

    @property
    def title(self) -> str:
        what = KIND_NAMES[self.kind]
        return f"{what}を追加" if self.index is None else f"{what}を編集"

    @property
    def rows(self) -> int:
        return len(self.fields) + 2              # 項目 + 決定 + 取消

    # ---------------------------------------------------------------- キー
    def on_key(self, ev: KeyEvent, c: str) -> None:
        if self.editing:
            self._key_edit(ev)
            return
        self.error = ""
        if c == "UP":
            self.row = (self.row - 1) % self.rows
        elif c in ("DOWN", "TAB"):
            self.row = (self.row + 1) % self.rows
        elif c == "ESC":
            self.closed = True
        elif c == "F2":
            self.submit()
        elif c in ("LEFT", "RIGHT"):
            if self.row < len(self.fields):
                self._cycle(self.fields[self.row], -1 if c == "LEFT" else 1)
        elif c in ("ENTER", " "):
            if self.row == len(self.fields):
                self.submit()
            elif self.row == len(self.fields) + 1:
                self.closed = True
            else:
                f = self.fields[self.row]
                if f.type in ("choice", "bool"):
                    self._cycle(f, 1)
                else:
                    self.editing = True
                    v = self.values[f.key]
                    self.buffer = show(f, v) if v not in (None, "") else ""

    def _cycle(self, f: Field, d: int) -> None:
        if f.type == "bool":
            self.values[f.key] = not self.values[f.key]
        elif f.type == "choice" and f.choices:
            cur = self.values[f.key]
            i = f.choices.index(cur) if cur in f.choices else -1
            self.values[f.key] = f.choices[(i + d) % len(f.choices)]

    def _key_edit(self, ev: KeyEvent) -> None:
        f = self.fields[self.row]
        if ev.key is Key.ENTER:
            text = self.buffer.strip()
            if f.type == "int":
                if text == "":
                    self.values[f.key] = None
                elif not text.isdigit():
                    self.error = f"{f.label} は 0 以上の整数で入力してください"
                    return
                else:
                    self.values[f.key] = int(text)
            elif f.type == "list":
                self.values[f.key] = [s for s in re.split(r"[\s,]+", text) if s]
            else:
                self.values[f.key] = text
            self.editing = False
        elif ev.key is Key.ESC:
            self.editing = False
        elif ev.key is Key.BACKSPACE:
            self.buffer = self.buffer[:-1]
        elif ev.key is Key.CHAR and ev.char.isprintable():
            self.buffer += ev.char

    def submit(self) -> None:
        for f in self.fields:
            v = self.values[f.key]
            if f.required and (v is None or v == ""):
                self.error = f"{f.label} を入力してください"
                return
            if f.type == "int" and v is None:
                self.error = f"{f.label} を入力してください"
                return
        v = self.values
        if self.kind == "npc":
            if not ID_RE.match(v["id"]):
                self.error = "ID は英小文字で始まり、英小文字・数字・_ だけで書いてください"
                return
            if text_width(v["glyph"]) != 2:
                self.error = f"文字「{v['glyph']}」の表示幅が {text_width(v['glyph'])} です。全角 1 文字にしてください"
                return
            bad = [s for s in v["route"] if s not in ROUTE_STEPS]
            if bad:
                self.error = f"道順に使えるのは {' / '.join(ROUTE_STEPS)} です（「{bad[0]}」）"
                return
            if v["move"] == "route" and not v["route"]:
                self.error = "動きが route のときは道順を入力してください"
                return
        if self.kind == "event" and re.search(r"\s", v["label"]):
            self.error = "ラベルに空白は使えません"
            return
        if self.validate:
            msg = self.validate(self, v)
            if msg:
                self.error = msg
                return
        out = {}
        for f in self.fields:
            val = v[f.key]
            empty = val == "" or val == [] or val is None
            if f.key not in self.original and (val == f.default or empty):
                continue                          # 既定の値は書かない
            out[f.key] = None if empty else val   # 空にした項目は消す
        self.result = out
        self.closed = True

    # ---------------------------------------------------------------- 描画
    def draw(self, buf: Buffer, title_style: Style) -> None:
        lw = max(text_width(f.label) for f in self.fields) + 2
        w = min(buf.width - 4, 64)
        h = self.rows + 3
        rect = Rect((buf.width - w) // 2, max(0, (buf.height - h) // 2), w, h)
        pos = f"（{self.original.get('x')}, {self.original.get('y')}）"
        inner = buf.box(rect, Style.of("bright_white"), title=f"{self.title} {pos}", title_style=title_style)
        y = inner.y
        for i, f in enumerate(self.fields):
            sel = i == self.row
            buf.put(inner.x + 1, y, f.label, LABEL)
            vx = inner.x + 1 + lw
            vw = inner.right - vx
            if sel and self.editing:
                text = truncate(self.buffer, vw - 1)
                buf.put(vx, y, " " * vw, EDIT)
                end = buf.put(vx, y, text, EDIT)
                buf.cursor = (end, y)
            else:
                mark = "‹ " if f.type in ("choice", "bool") and sel else ""
                text = show(f, self.values[f.key]) + (" ›" if mark else "")
                st = HILITE if sel else (DIM if text.startswith("（なし）") else TEXT)
                buf.put(vx, y, truncate(mark + text, vw), st)
            y += 1
        y += 1
        for j, label in enumerate(("［決定］", "［取消］")):
            st = HILITE if self.row == len(self.fields) + j else TEXT
            buf.put(inner.x + 1 + j * 10, y, label, st)
        y += 1
        if self.error:
            buf.put(inner.x + 1, y, truncate(self.error, inner.w - 2), ERR)
        else:
            hint = "Enter：入力・切替　↑↓：項目　F2：決定　Esc：取消"
            buf.put(inner.x + 1, y, truncate(hint, inner.w - 2), DIM)
