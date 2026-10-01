"""マップエディタ（要件 T-02）：端末で動く TUI。エンジンの描画・入力をそのまま使う。

    python -m trpg.tools.map_editor scenarios/FirstQuest
    python -m trpg.tools.map_editor scenarios/FirstQuest --map town_bern

3-3a：マップを開いて表示・スクロール、タイルを塗る、Map.data に保存する。
3-3b：NPC・ワープ・イベントを置く・編集する・動かす・消す。
3-3c：マップの新規作成・大きさの変更、範囲の塗りつぶし・コピー・貼り付け。

保存は Map.data のうち変えたところ（マップの ``rows`` と NPC などの表の項目）だけを書き換える（コメントや書式は残る）。
最初の保存の前に元のファイルを Map.data.bak に写す。保存後に --check と同じ検証をして件数を出す。
"""
from __future__ import annotations

import argparse
import os
import sys
import unicodedata
from pathlib import Path
from typing import Optional

from ..app import App, Scene
from ..data import GameData, Report, load_game_data
from ..data.models import GameMap, Tile
from ..package import PackageError, open_package
from ..package.check import check_package
from ..term import Buffer, Key, KeyEvent, Rect, Style, set_ambiguous_width, text_width, truncate
from . import mapfile
from .mapfile import MapFileError, read_objects, replace_rows
from .objform import KIND_NAMES, ORDER, ObjectForm

MAP_FILE = "Map.data"
PANEL_W = 34
UNDO_LIMIT = 500
UNKNOWN_GLYPH = "？"
WARP_GLYPH = "Ｗ"
EVENT_GLYPH = "Ｅ"

FRAME = Style.of("white")
TITLE = Style.of("bright_white", bold=True)
TEXT = Style()
DIM = Style.of("gray")
HILITE = Style.of("black", "bright_yellow")
MSG = Style.of("bright_yellow")
ERR = Style.of("bright_red")

HELP = [
    ("矢印", "カーソル移動（PgUp/PgDn/Home/End で大きく）"),
    ("Enter / Space", "今のタイルで塗る"),
    ("[ ] / Tab", "タイルを選ぶ（1〜9 で直接）"),
    ("i", "カーソルの下のタイルを選ぶ（スポイト）"),
    ("p", "ペン：オンの間は動いた先を塗る"),
    ("v", "範囲を選ぶ → f：塗りつぶし　c：コピー　Esc：やめる"),
    ("b", "コピーした範囲をカーソルの位置に貼り付け"),
    ("r", "マップの大きさを変える（右・下を増減）"),
    ("u", "元に戻す"),
    ("n / w / e", "カーソルの位置に NPC / ワープ / イベントを置く"),
    ("c", "カーソルの位置の NPC などを編集"),
    ("g", "カーソルの位置の NPC などを動かす（Enter で置く）"),
    ("x / Delete", "カーソルの位置の NPC などを消す"),
    ("o", "NPC・ワープ・イベントの表示／非表示"),
    ("m", "マップを切り替える（一覧で a：新しいマップ）"),
    ("s / F2", "保存（編集したマップすべて）"),
    ("q / Esc", "終わる"),
    ("? / F1", "この説明"),
]


def _cmd(ev: KeyEvent) -> str:
    """文字キーを半角小文字に揃える（IME がオンのままでも使えるように）。"""
    if ev.key is Key.CHAR:
        return unicodedata.normalize("NFKC", ev.char).lower()
    return ev.key.value


class EditorScene(Scene):
    accepts_text = True        # 全角で届いたキーも受け付ける（IME の警告を出さない）

    def __init__(self, root: Path, gd: GameData, map_id: Optional[str] = None, report: Optional[Report] = None):
        self.root = Path(root)
        self.gd = gd
        self.rows: dict[str, list[str]] = {mid: list(m.rows) for mid, m in gd.maps.items()}
        self.saved_rows = {mid: list(r) for mid, r in self.rows.items()}
        self.text = (self.root / MAP_FILE).read_bytes().decode("utf-8-sig")
        self.objs = read_objects(self.text)
        self.saved_objs = read_objects(self.text)
        self.history: list[tuple] = []          # 元に戻すための記録（("tile", マップ, x, y, 前の文字) / ("text", マップ, x, y, 前の本文)）
        self.map_id = map_id if map_id in gd.maps else next(iter(gd.maps))
        self.x = self.y = 0
        self.ox = self.oy = 0
        self.brush: dict[str, int] = {}         # タイルセットごとの選択中のタイル
        self.pen = False
        self.show_objects = True
        self.mode = "edit"                      # edit | maps | quit | help | form | pick | move | delete
        self.form: Optional[ObjectForm] = None
        self.picking: list[tuple[str, int]] = []  # 同じマスに複数あるときの候補
        self.pick_action = ""
        self.target: Optional[tuple[str, int]] = None   # 動かす・消す対象（種類, 何番目）
        self.anchor: Optional[tuple[int, int]] = None   # 範囲選択の始点
        self.clip: Optional[list[str]] = None            # コピーした範囲
        self.list_i = 0
        self.message = ""
        self.message_style = MSG
        self.backed_up = False
        if report is not None and report.issues:
            self.say(f"読み込み時の検証：エラー {len(report.errors)} 件 / 警告 {len(report.warnings)} 件"
                     "（--check で詳細）", ERR if report.errors else MSG)

    # ---------------------------------------------------------------- 状態
    @property
    def map(self) -> GameMap:
        return self.gd.maps[self.map_id]

    @property
    def tiles(self) -> list[Tile]:
        ts = self.gd.tilesets.get(self.map.tileset)
        return list(ts.tiles.values()) if ts else []

    @property
    def brush_i(self) -> int:
        n = len(self.tiles)
        return min(self.brush.get(self.map.tileset, 0), max(0, n - 1))

    @property
    def width(self) -> int:
        r = self.rows[self.map_id]
        return len(r[0]) if r else 0

    @property
    def height(self) -> int:
        return len(self.rows[self.map_id])

    def tile_at(self, x: int, y: int) -> Optional[Tile]:
        ts = self.gd.tilesets.get(self.map.tileset)
        return ts.tiles.get(self.rows[self.map_id][y][x]) if ts else None

    @property
    def dirty(self) -> set[str]:
        """保存していない変更のあるマップ。"""
        return {mid for mid in self.rows
                if self.rows[mid] != self.saved_rows.get(mid) or self.objs.get(mid) != self.saved_objs.get(mid)}

    def objects_at(self, x: int, y: int) -> list[tuple[str, int, dict]]:
        out = []
        for kind in mapfile.KINDS:
            for i, o in enumerate(self.objs.get(self.map_id, {}).get(kind, [])):
                if (o.get("x"), o.get("y")) == (x, y):
                    out.append((kind, i, o))
        return out

    def obj(self, kind: str, index: int) -> dict:
        return self.objs[self.map_id][kind][index]

    def say(self, text: str, style: Style = MSG) -> None:
        self.message = text
        self.message_style = style

    # ---------------------------------------------------------------- 編集
    def paint(self) -> None:
        tiles = self.tiles
        if not tiles or not self.height:
            return
        ch = tiles[self.brush_i].char
        rows = self.rows[self.map_id]
        old = rows[self.y][self.x]
        if old == ch:
            return
        rows[self.y] = rows[self.y][: self.x] + ch + rows[self.y][self.x + 1:]
        self._record(("tile", self.map_id, self.x, self.y, old))

    def _record(self, entry: tuple) -> None:
        self.history.append(entry)
        del self.history[:-UNDO_LIMIT]

    def apply(self, fn, *args) -> bool:
        """Map.data の本文を書き換える操作（NPC などの追加・編集・移動・削除）。"""
        try:
            new = fn(self.text, self.map_id, *args)
        except MapFileError as e:
            self.say(f"書き換えられません：{e}", ERR)
            return False
        self._record(("text", self.map_id, self.x, self.y, self.text))
        self.text = new
        self.objs = read_objects(new)
        return True

    def undo_last(self) -> None:
        if not self.history:
            self.say("元に戻す操作はありません")
            return
        kind, mid, x, y, old = self.history.pop()
        if mid != self.map_id:
            self.open_map(mid)
        if kind == "tile":
            rows = self.rows[mid]
            rows[y] = rows[y][:x] + old + rows[y][x + 1:]
        elif kind == "rows":
            self.rows[mid] = old
        elif kind == "newmap":
            text, prev = old
            self.text = text
            self.objs = read_objects(text)
            del self.rows[mid], self.gd.maps[mid]
            self.open_map(prev)
            self.say(f"マップ {mid} の追加を取り消しました")
            return
        else:
            self.text = old
            self.objs = read_objects(old)
        self.x, self.y = x, y

    def pick(self) -> None:
        ch = self.rows[self.map_id][self.y][self.x]
        for i, t in enumerate(self.tiles):
            if t.char == ch:
                self.brush[self.map.tileset] = i
                return
        self.say(f"「{ch}」はタイルセットにありません", ERR)

    def select_brush(self, i: int) -> None:
        n = len(self.tiles)
        if n:
            self.brush[self.map.tileset] = i % n

    def move(self, dx: int, dy: int) -> None:
        if not self.height:
            return
        self.x = min(max(self.x + dx, 0), self.width - 1)
        self.y = min(max(self.y + dy, 0), self.height - 1)
        if self.pen:
            self.paint()

    def open_map(self, map_id: str) -> None:
        self.map_id = map_id
        self.x = min(self.x, max(0, self.width - 1))
        self.y = min(self.y, max(0, self.height - 1))
        self.ox = self.oy = 0
        self.pen = False

    # ---------------------------------------------------------------- 範囲・大きさ・新しいマップ（3-3c）
    def sel_rect(self) -> tuple[int, int, int, int]:
        ax, ay = self.anchor if self.anchor else (self.x, self.y)
        return min(ax, self.x), min(ay, self.y), max(ax, self.x), max(ay, self.y)

    def _set_rows(self, rows: list[str]) -> None:
        if rows == self.rows[self.map_id]:
            return
        self._record(("rows", self.map_id, self.x, self.y, list(self.rows[self.map_id])))
        self.rows[self.map_id] = rows

    def fill_rect(self) -> None:
        tiles = self.tiles
        if not tiles:
            return
        ch = tiles[self.brush_i].char
        x0, y0, x1, y1 = self.sel_rect()
        rows = list(self.rows[self.map_id])
        for y in range(y0, y1 + 1):
            rows[y] = rows[y][:x0] + ch * (x1 - x0 + 1) + rows[y][x1 + 1:]
        self._set_rows(rows)
        self.say(f"{x1 - x0 + 1}×{y1 - y0 + 1} を「{tiles[self.brush_i].name or ch}」で塗りつぶしました")

    def copy_rect(self) -> None:
        x0, y0, x1, y1 = self.sel_rect()
        self.clip = [r[x0:x1 + 1] for r in self.rows[self.map_id][y0:y1 + 1]]
        self.say(f"{x1 - x0 + 1}×{y1 - y0 + 1} をコピーしました（b で貼り付け）")

    def paste(self) -> None:
        if not self.clip:
            self.say("コピーした範囲がありません（v で範囲を選んで c）")
            return
        rows = list(self.rows[self.map_id])
        w = min(len(self.clip[0]), self.width - self.x)
        h = min(len(self.clip), self.height - self.y)
        for i in range(h):
            y = self.y + i
            rows[y] = rows[y][:self.x] + self.clip[i][:w] + rows[y][self.x + w:]
        self._set_rows(rows)
        cut = "（はみ出た分は切り捨て）" if (w, h) != (len(self.clip[0]), len(self.clip)) else ""
        self.say(f"{w}×{h} を貼り付けました{cut}")

    def tile_choices(self, tileset: str) -> list[str]:
        ts = self.gd.tilesets.get(tileset)
        return list(ts.tiles) if ts else []

    def open_resize(self) -> None:
        if not self.tiles:
            self.say("タイルセットがないので大きさを変えられません", ERR)
            return
        fill = self.tiles[self.brush_i].char
        self.form = ObjectForm("resize", {"width": self.width, "height": self.height, "fill": fill},
                               list(self.gd.maps), validate=self._validate,
                               choices={"fill": self.tile_choices(self.map.tileset)})
        self.mode = "form"

    def resize(self, w: int, h: int, fill: str) -> None:
        rows = [r[:w] + fill * max(0, w - len(r)) for r in self.rows[self.map_id][:h]]
        rows += [fill * w] * max(0, h - len(rows))
        old = (self.width, self.height)
        self._set_rows(rows)
        self.x, self.y = min(self.x, w - 1), min(self.y, h - 1)
        self.say(f"大きさを {old[0]}×{old[1]} から {w}×{h} に変えました")

    def open_new_map(self) -> None:
        tilesets = list(self.gd.tilesets)
        if not tilesets:
            self.say("タイルセットがありません", ERR)
            return
        ts = self.map.tileset if self.map.tileset in self.gd.tilesets else tilesets[0]
        chars = self.tile_choices(ts)
        n = 1
        while f"map{n}" in self.gd.maps:
            n += 1
        self.form = ObjectForm("map", {"id": f"map{n}", "name": "新しいマップ", "tileset": ts, "width": 20,
                                       "height": 15, "fill": chars[0] if chars else "", "dark": False,
                                       "indoor": False},
                               list(self.gd.maps), validate=self._validate,
                               choices={"tileset": tilesets, "fill": chars})
        self.mode = "form"

    def add_map(self, v: dict) -> None:
        if v["fill"] not in self.tile_choices(v["tileset"]):
            self.say(f"タイル「{v['fill']}」はタイルセット {v['tileset']} にありません", ERR)
            return
        rows = [v["fill"] * v["width"]] * v["height"]
        values = {"id": v["id"], "name": v["name"], "tileset": v["tileset"],
                  "dark": True if v["dark"] else None, "indoor": True if v["indoor"] else None}
        try:
            new = mapfile.add_map(self.text, values, rows)
        except MapFileError as e:
            self.say(f"追加できません：{e}", ERR)
            return
        self._record(("newmap", v["id"], self.x, self.y, (self.text, self.map_id)))
        self.text = new
        self.objs = read_objects(new)
        self.gd.maps[v["id"]] = GameMap(id=v["id"], name=v["name"], tileset=v["tileset"], rows=list(rows),
                                        dark=v["dark"], indoor=v["indoor"])
        self.rows[v["id"]] = list(rows)
        self.open_map(v["id"])
        self.x = self.y = 0
        self.say(f"マップ {v['id']}（{v['width']}×{v['height']}）を作りました。s で保存します")

    def _key_select(self, c: str) -> None:
        moves = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0),
                 "PGUP": (0, -10), "PGDN": (0, 10)}
        if c in moves:
            self.move(*moves[c])
        elif c == "HOME":
            self.move(-self.x, 0)
        elif c == "END":
            self.move(self.width - 1 - self.x, 0)
        elif c in ("f", "ENTER", " "):
            self.fill_rect()
            self.mode, self.anchor = "edit", None
        elif c in ("c", "y"):
            self.copy_rect()
            self.mode, self.anchor = "edit", None
        elif c in ("ESC", "v", "q"):
            self.mode, self.anchor = "edit", None
            self.say("")

    def save(self) -> bool:
        dirty = self.dirty
        if not dirty:
            self.say("変更はありません")
            return True
        path = self.root / MAP_FILE
        try:
            raw = path.read_bytes()
            out = self.text
            in_text = {m["id"]: m.get("rows") for m in mapfile.tomllib.loads(out).get("map", [])}
            for mid in self.rows:
                if in_text.get(mid) != self.rows[mid]:
                    out = replace_rows(out, mid, self.rows[mid])
        except (OSError, MapFileError) as e:
            self.say(f"保存できません：{e}", ERR)
            return False
        if not self.backed_up:
            (self.root / (MAP_FILE + ".bak")).write_bytes(raw)
            self.backed_up = True
        data = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + out.encode("utf-8")
        tmp = path.with_name(MAP_FILE + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        self.text = out
        self.saved_rows = {mid: list(r) for mid, r in self.rows.items()}
        self.objs = read_objects(out)
        self.saved_objs = read_objects(out)
        saved = len(dirty)
        rep, _ = check_package(self.root, lambda s: None)
        first = rep.errors[0].format() if rep.errors else ""
        self.say(f"保存しました（{saved} マップ）。検証：エラー {len(rep.errors)} 件 / 警告 {len(rep.warnings)} 件"
                 + (f"  {first}" if first else ""), ERR if rep.errors else MSG)
        return True

    # ---------------------------------------------------------------- キー
    def on_key(self, ev: KeyEvent, actions) -> None:
        c = _cmd(ev)
        if self.mode == "help":
            self.mode = "edit"
            return
        if self.mode == "form":
            self.form.on_key(ev, c)
            if self.form.closed:
                self._finish_form()
            return
        if self.mode == "pick":
            self._key_pick(c)
            return
        if self.mode == "move":
            self._key_move(c)
            return
        if self.mode == "select":
            self._key_select(c)
            return
        if self.mode == "delete":
            if c == "y":
                kind, i = self.target
                name = self._obj_name(kind, self.obj(kind, i))
                if self.apply(mapfile.delete_object, kind, i):
                    self.say(f"{name} を消しました")
            else:
                self.say("")
            self.mode = "edit"
            return
        if self.mode == "maps":
            self._key_maps(ev, c)
            return
        if self.mode == "quit":
            if c == "y":
                if self.save():
                    self.app.quit()
            elif c == "n":
                self.app.quit()
            else:
                self.mode = "edit"
                self.say("")
            return
        self.say("")
        page = 10
        moves = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0),
                 "PGUP": (0, -page), "PGDN": (0, page)}
        if c in moves:
            self.move(*moves[c])
        elif c == "HOME":
            self.move(-self.x, 0)
        elif c == "END":
            self.move(self.width - 1 - self.x, 0)
        elif c in ("ENTER", " "):
            self.paint()
        elif c in ("]", "TAB"):
            self.select_brush(self.brush_i + 1)
        elif c == "[":
            self.select_brush(self.brush_i - 1)
        elif len(c) == 1 and c in "123456789":
            if int(c) <= len(self.tiles):
                self.select_brush(int(c) - 1)
        elif c == "i":
            self.pick()
        elif c == "p":
            self.pen = not self.pen
            if self.pen:
                self.paint()
        elif c == "u":
            self.undo_last()
        elif c == "v":
            if self.height:
                self.pen = False
                self.anchor = (self.x, self.y)
                self.mode = "select"
                self.say("範囲を選びます：矢印で広げる　f：塗りつぶし　c：コピー　Esc：やめる")
        elif c == "b":
            self.paste()
        elif c == "r":
            self.open_resize()
        elif c in ("n", "w", "e"):
            self.new_object({"n": "npc", "w": "warp", "e": "event"}[c])
        elif c in ("c", "g", "x", "DELETE"):
            self.choose_object({"c": "edit", "g": "move", "x": "delete", "DELETE": "delete"}[c])
        elif c == "o":
            self.show_objects = not self.show_objects
        elif c == "m":
            self.mode = "maps"
            self.list_i = list(self.gd.maps).index(self.map_id)
        elif c in ("s", "F2"):
            self.save()
        elif c in ("q", "ESC"):
            if self.dirty:
                self.mode = "quit"
            else:
                self.app.quit()
        elif c in ("?", "F1"):
            self.mode = "help"

    # ---------------------------------------------------------------- NPC・ワープ・イベント
    def _obj_name(self, kind: str, o: dict) -> str:
        if kind == "npc":
            return f"NPC {o.get('id', '')}"
        if kind == "warp":
            return f"ワープ（→ {o.get('to', '')}）"
        return f"イベント {o.get('label', '')}"

    def new_object(self, kind: str) -> None:
        if not self.height:
            return
        base = {"x": self.x, "y": self.y}
        if kind == "npc":
            ids = {o.get("id") for o in self.objs[self.map_id]["npc"]}
            n = 1
            while f"npc{n}" in ids:
                n += 1
            base.update(id=f"npc{n}", glyph="人")
        elif kind == "warp":
            others = [m for m in self.gd.maps if m != self.map_id] or [self.map_id]
            base.update(to=others[0], tx=0, ty=0)
        self.form = ObjectForm(kind, base, list(self.gd.maps), validate=self._validate)
        self.form.original = {"x": self.x, "y": self.y}      # 新規：x・y 以外は既定値なら書かない
        self.mode = "form"
        self.show_objects = True

    def choose_object(self, action: str) -> None:
        here = self.objects_at(self.x, self.y) if self.show_objects else []
        if not here:
            self.say("カーソルの位置に NPC・ワープ・イベントはありません" if self.show_objects
                     else "NPC などを表示していません（o で表示）")
            return
        if len(here) == 1:
            self._do(action, here[0][0], here[0][1])
            return
        self.picking = [(k, i) for k, i, _ in here]
        self.pick_action = action
        self.list_i = 0
        self.mode = "pick"

    def _do(self, action: str, kind: str, i: int) -> None:
        self.target = (kind, i)
        if action == "edit":
            self.form = ObjectForm(kind, self.obj(kind, i), list(self.gd.maps), index=i, validate=self._validate)
            self.mode = "form"
        elif action == "move":
            self.mode = "move"
            self.say(f"{self._obj_name(kind, self.obj(kind, i))} を動かします。矢印で移動、Enter で置く、Esc でやめる")
        else:
            self.mode = "delete"

    def _key_pick(self, c: str) -> None:
        if c == "UP":
            self.list_i = (self.list_i - 1) % len(self.picking)
        elif c == "DOWN":
            self.list_i = (self.list_i + 1) % len(self.picking)
        elif c in ("ENTER", " "):
            self.mode = "edit"
            self._do(self.pick_action, *self.picking[self.list_i])
        elif c in ("ESC", "q"):
            self.mode = "edit"

    def _key_move(self, c: str) -> None:
        moves = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
        kind, i = self.target
        o = self.obj(kind, i)
        if c in moves:
            dx, dy = moves[c]
            self.x = min(max(self.x + dx, 0), self.width - 1)
            self.y = min(max(self.y + dy, 0), self.height - 1)
        elif c in ("ENTER", " ", "g"):
            self.mode = "edit"
            if (self.x, self.y) == (o.get("x"), o.get("y")):
                self.say("")
                return
            name = self._obj_name(kind, o)
            if self.apply(mapfile.set_object, kind, i, {"x": self.x, "y": self.y}):
                self.say(f"{name} を ({self.x}, {self.y}) に動かしました")
        elif c in ("ESC", "q"):
            self.mode = "edit"
            self.x, self.y = o.get("x", self.x), o.get("y", self.y)
            self.say("動かすのをやめました")

    def _validate(self, form: ObjectForm, v: dict) -> str:
        if form.kind == "map" and v["id"] in self.gd.maps:
            return f"マップ {v['id']} はすでにあります"
        if form.kind == "resize":
            for kind in mapfile.KINDS:
                for o in self.objs.get(self.map_id, {}).get(kind, []):
                    if not (o.get("x", 0) < v["width"] and o.get("y", 0) < v["height"]):
                        return (f"{self._obj_name(kind, o)}（{o.get('x')}, {o.get('y')}）がマップの外に出ます。"
                                "先に動かすか消してください")
        if form.kind == "npc":
            for j, o in enumerate(self.objs[self.map_id]["npc"]):
                if o.get("id") == v["id"] and j != form.index:
                    return f"ID「{v['id']}」はこのマップで使われています"
        if form.kind == "warp":
            rows = self.rows.get(v["to"])
            if rows is not None and not (v["tx"] < len(rows[0]) and v["ty"] < len(rows)):
                return f"行き先 ({v['tx']}, {v['ty']}) がマップ {v['to']}（{len(rows[0])}×{len(rows)}）の外です"
        return ""

    def _finish_form(self) -> None:
        form = self.form
        self.form = None
        self.mode = "edit"
        if form.result is None:
            self.say("")
            return
        if form.kind == "resize":
            self.resize(form.values["width"], form.values["height"], form.values["fill"])
            return
        if form.kind == "map":
            self.add_map(form.values)
            return
        if form.index is None:
            vals = {"x": form.original["x"], "y": form.original["y"]}
            vals.update({k: v for k, v in form.result.items() if v is not None})
            order = ORDER[form.kind]
            vals = dict(sorted(vals.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99))
            if self.apply(mapfile.add_object, form.kind, vals):
                self.say(f"{self._obj_name(form.kind, vals)} を置きました")
        else:
            changes = {k: v for k, v in form.result.items() if form.original.get(k) != v}
            if not changes:
                self.say("変更はありません")
            elif self.apply(mapfile.set_object, form.kind, form.index, changes):
                self.say(f"{self._obj_name(form.kind, self.obj(form.kind, form.index))} を書き換えました")

    def _key_maps(self, ev: KeyEvent, c: str) -> None:
        ids = list(self.gd.maps)
        if c == "UP":
            self.list_i = (self.list_i - 1) % len(ids)
        elif c == "DOWN":
            self.list_i = (self.list_i + 1) % len(ids)
        elif c in ("ENTER", " "):
            self.open_map(ids[self.list_i])
            self.mode = "edit"
        elif c == "a":
            self.open_new_map()
        elif c in ("ESC", "q", "m"):
            self.mode = "edit"

    # ---------------------------------------------------------------- 描画
    def draw(self, buf: Buffer) -> None:
        W, H = buf.width, buf.height
        map_rect = Rect(0, 0, W - PANEL_W, H - 1)
        panel_rect = Rect(W - PANEL_W, 0, PANEL_W, H - 1)
        m = self.map
        title = f"{m.name}（{m.id}） {self.width}×{self.height}{' *' if self.map_id in self.dirty else ''}"
        inner = buf.box(map_rect, FRAME, title=truncate(title, map_rect.w - 4), title_style=TITLE)
        self._draw_map(buf, inner)
        self._draw_panel(buf, buf.box(panel_rect, FRAME, title="タイル", title_style=TITLE))
        self._draw_status(buf, H - 1, W)
        if self.mode == "maps":
            self._draw_map_list(buf)
        elif self.mode == "help":
            self._draw_help(buf)
        elif self.mode == "form":
            self.form.draw(buf, TITLE)
        elif self.mode == "pick":
            self._draw_pick(buf)
        elif self.mode == "delete":
            kind, i = self.target
            self._draw_dialog(buf, [f"{self._obj_name(kind, self.obj(kind, i))} を消しますか？", "y：消す　それ以外：やめる"])
        elif self.mode == "quit":
            self._draw_dialog(buf, ["保存していない変更があります。",
                                    "y：保存して終わる　n：保存せずに終わる　Esc：戻る"])

    def _scroll(self, cols: int, rows: int) -> None:
        """カーソルが表示範囲の端から 2 マス以内に来たらずらす。"""
        margin_x = min(2, max(0, (cols - 1) // 2))
        margin_y = min(2, max(0, (rows - 1) // 2))
        if self.x < self.ox + margin_x:
            self.ox = self.x - margin_x
        elif self.x > self.ox + cols - 1 - margin_x:
            self.ox = self.x - cols + 1 + margin_x
        if self.y < self.oy + margin_y:
            self.oy = self.y - margin_y
        elif self.y > self.oy + rows - 1 - margin_y:
            self.oy = self.y - rows + 1 + margin_y
        self.ox = min(max(0, self.ox), max(0, self.width - cols))
        self.oy = min(max(0, self.oy), max(0, self.height - rows))

    def _draw_map(self, buf: Buffer, area: Rect) -> None:
        cols, rows = area.w // 2, area.h
        self._scroll(cols, rows)
        ox, oy = self.ox, self.oy
        px = area.x + max(0, (cols - self.width) // 2) * 2
        py = area.y + max(0, (rows - self.height) // 2)
        grid = self.rows[self.map_id]
        sel = self.sel_rect() if self.mode == "select" else None
        for ty in range(min(rows, self.height - oy)):
            for tx in range(min(cols, self.width - ox)):
                mx, my = ox + tx, oy + ty
                glyph, st = self._cell(grid, mx, my)
                if sel and sel[0] <= mx <= sel[2] and sel[1] <= my <= sel[3]:
                    st = st._replace(bg=4)                      # 選んだ範囲は青い背景
                if mx == self.x and my == self.y:
                    st = st._replace(attrs=st.attrs | 8)       # 反転表示
                buf.put(px + tx * 2, py + ty, glyph, st, clip=area)

    def _cell(self, grid: list[str], x: int, y: int) -> tuple[str, Style]:
        if self.show_objects:
            moving = self.target if self.mode == "move" else None
            if moving and (x, y) == (self.x, self.y):
                return self._glyph(moving[0], self.obj(*moving))
            for kind, i, o in self.objects_at(x, y):
                if (kind, i) != moving:
                    return self._glyph(kind, o)
        tile = self.tile_at(x, y)
        if tile is None:
            return UNKNOWN_GLYPH, Style.of("bright_red")
        return tile.glyph, Style.of(tile.color) if tile.color else Style()

    def _glyph(self, kind: str, o: dict) -> tuple[str, Style]:
        if kind == "npc":
            g = o.get("glyph", "")
            return (g if text_width(g) == 2 else UNKNOWN_GLYPH), Style.of(o.get("color") or "white", bold=True)
        if kind == "warp":
            return WARP_GLYPH, Style.of("bright_magenta", bold=True)
        return EVENT_GLYPH, Style.of("bright_cyan", bold=True)

    def _draw_panel(self, buf: Buffer, area: Rect) -> None:
        tiles = self.tiles
        info = self._cursor_info()
        list_h = max(1, area.h - len(info) - 2)
        first = max(0, min(self.brush_i - list_h // 2, len(tiles) - list_h))
        y = area.y
        for i in range(first, min(len(tiles), first + list_h)):
            t = tiles[i]
            num = str(i + 1) if i < 9 else " "
            line = f"{num} {t.char} {t.glyph} {t.name or ''}"
            pas = "通" if t.passable else "壁"
            st = HILITE if i == self.brush_i else TEXT
            buf.put(area.x, y, " " * area.w, st)
            buf.put(area.x, y, truncate(line, area.w - 3), st, clip=area)
            buf.put(area.right - 2, y, pas, st if i == self.brush_i else DIM, clip=area)
            if i != self.brush_i and t.color:
                buf.put(area.x + 4, y, t.glyph, Style.of(t.color), clip=area)
            y += 1
        y = area.bottom - len(info)
        buf.put(area.x, y - 1, "─" * area.w, DIM, clip=area)
        for text, st in info:
            buf.put(area.x, y, truncate(text, area.w), st, clip=area)
            y += 1

    def _cursor_info(self) -> list[tuple[str, Style]]:
        out: list[tuple[str, Style]] = []
        if self.height:
            ch = self.rows[self.map_id][self.y][self.x]
            t = self.tile_at(self.x, self.y)
            out.append((f"位置 ({self.x}, {self.y})", TEXT))
            out.append((f"下のタイル {ch} {t.glyph + ' ' + t.name if t else '（未定義）'}", TEXT if t else ERR))
            for kind, _, o in self.objects_at(self.x, self.y):
                if kind == "npc":
                    out.append((f"NPC {o.get('id')}（{o.get('move', 'fixed')}）", TEXT))
                elif kind == "warp":
                    out.append((f"ワープ → {o.get('to')} ({o.get('tx')}, {o.get('ty')})", TEXT))
                else:
                    out.append((f"イベント {o.get('label')}（{o.get('trigger', 'check')}）", TEXT))
        if self.mode == "select":
            x0, y0, x1, y1 = self.sel_rect()
            out.append((f"範囲 ({x0}, {y0})〜({x1}, {y1})  {x1 - x0 + 1}×{y1 - y0 + 1}", MSG))
        if self.clip:
            out.append((f"コピー {len(self.clip[0])}×{len(self.clip)}（b で貼り付け）", DIM))
        out.append((f"ペン {'オン' if self.pen else 'オフ'}　表示 {'オン' if self.show_objects else 'オフ'}", DIM))
        out.append(("? で操作説明", DIM))
        return out

    def _draw_status(self, buf: Buffer, y: int, w: int) -> None:
        if self.message:
            buf.put(1, y, truncate(self.message, w - 2), self.message_style)
        else:
            changed = f"　未保存 {len(self.dirty)} マップ" if self.dirty else ""
            buf.put(1, y, truncate("矢印：移動  Enter：塗る  [ ]：タイル  n/w/e：置く  c：編集  g：動かす  x：消す  "
                                   "v：範囲  b：貼付  r：大きさ  s：保存  ?：説明" + changed, w - 2), DIM)

    def _overlay(self, buf: Buffer, w: int, h: int, title: str) -> Rect:
        rect = Rect(max(0, (buf.width - w) // 2), max(0, (buf.height - h) // 2), min(w, buf.width), min(h, buf.height))
        return buf.box(rect, Style.of("bright_white"), title=title, title_style=TITLE)

    def _draw_map_list(self, buf: Buffer) -> None:
        ids = list(self.gd.maps)
        h = min(len(ids) + 2, buf.height - 4)
        inner = self._overlay(buf, 60, h, "マップ（Enter：開く　a：新しいマップ　Esc：戻る）")
        first = max(0, min(self.list_i - inner.h // 2, len(ids) - inner.h))
        for row, i in enumerate(range(first, min(len(ids), first + inner.h))):
            m = self.gd.maps[ids[i]]
            mark = "*" if ids[i] in self.dirty else " "
            rows = self.rows[ids[i]]
            size = f"{len(rows[0]) if rows else 0}×{len(rows)}"
            line = f"{mark} {m.id:<16} {size:>7}  {m.name}"
            st = HILITE if i == self.list_i else TEXT
            buf.put(inner.x, inner.y + row, " " * inner.w, st)
            buf.put(inner.x, inner.y + row, truncate(line, inner.w), st, clip=inner)

    def _draw_pick(self, buf: Buffer) -> None:
        inner = self._overlay(buf, 50, len(self.picking) + 2, "どれにしますか（Enter / Esc）")
        for row, (kind, i) in enumerate(self.picking):
            st = HILITE if row == self.list_i else TEXT
            buf.put(inner.x, inner.y + row, " " * inner.w, st)
            buf.put(inner.x + 1, inner.y + row, truncate(self._obj_name(kind, self.obj(kind, i)), inner.w - 2), st)

    def _draw_help(self, buf: Buffer) -> None:
        inner = self._overlay(buf, 70, len(HELP) + 4, "操作説明（何かキーを押すと戻る）")
        kw = max(text_width(k) for k, _ in HELP) + 2
        for i, (k, d) in enumerate(HELP):
            buf.put(inner.x + 1, inner.y + i, k, Style.of("bright_cyan"), clip=inner)
            buf.put(inner.x + 1 + kw, inner.y + i, d, TEXT, clip=inner)
        buf.put(inner.x + 1, inner.bottom - 1, "NPC は Map.data の文字、Ｗ はワープ、Ｅ はイベント", DIM, clip=inner)

    def _draw_dialog(self, buf: Buffer, lines: list[str]) -> None:
        inner = self._overlay(buf, max(text_width(s) for s in lines) + 6, len(lines) + 2, "")
        for i, s in enumerate(lines):
            buf.put(inner.x + 2, inner.y + i, s, TEXT, clip=inner)


def load(folder: Path | str) -> tuple[Path, GameData, Report]:
    """エディタで開くシナリオのフォルダを読む。開けなければ PackageError。"""
    root = Path(folder)
    if not root.is_dir():
        raise PackageError(f"シナリオのフォルダを指定してください（zip は編集できません）: {folder}")
    rep = Report()
    with open_package(root, rep) as pkg:
        gd = load_game_data(pkg, rep)
    if not gd.maps:
        raise PackageError("Map.data にマップがありません（読み込めないか、[[map]] がありません）\n" + rep.format())
    return root, gd, rep


def main(argv: list[str] | None = None) -> int:
    from ..__main__ import _stdout_utf8
    from ..data import DataError
    from ..term import TerminalError
    _stdout_utf8()
    p = argparse.ArgumentParser(prog="python -m trpg.tools.map_editor", description="マップエディタ（TUI）")
    p.add_argument("folder", help="シナリオのフォルダ（manifest.toml のあるフォルダ）")
    p.add_argument("--map", metavar="ID", help="最初に開くマップの ID")
    p.add_argument("--ambiguous-width", type=int, choices=(1, 2), default=1, help="曖昧幅文字の幅")
    p.add_argument("--no-color", action="store_true", help="色を使わない")
    args = p.parse_args(argv)
    try:
        root, gd, rep = load(args.folder)
    except PackageError as e:
        print(f"開けません: {e}", file=sys.stderr)
        return 1
    except DataError as e:
        print(f"開けません:\n{e.report.format()}", file=sys.stderr)
        return 1
    if args.map and args.map not in gd.maps:
        print(f"マップ {args.map} がありません（{', '.join(gd.maps)}）", file=sys.stderr)
        return 1
    set_ambiguous_width(args.ambiguous_width)
    app = App(EditorScene(root, gd, args.map, rep), use_color=not args.no_color)
    try:
        app.run()
    except TerminalError as e:
        print(f"起動できません:\n{e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
