"""マップエディタ（要件 T-02）：端末で動く TUI。エンジンの描画・入力をそのまま使う。

    python -m trpg.tools.map_editor scenarios/FirstQuest
    python -m trpg.tools.map_editor scenarios/FirstQuest --map town_bern

3-3a の範囲：マップを開いて表示・スクロール、タイルを塗る、Map.data に保存する。
NPC・ワープ・イベントは表示だけ（置く・動かすのは 3-3b）。

保存は Map.data のうち編集したマップの ``rows`` だけを書き換える（コメントや書式は残る）。
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
from .mapfile import MapFileError, replace_rows

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
    ("u", "元に戻す"),
    ("o", "NPC・ワープ・イベントの表示／非表示"),
    ("m", "マップを切り替える"),
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
        self.undo: dict[str, list[tuple[int, int, str]]] = {mid: [] for mid in gd.maps}
        self.dirty: set[str] = set()
        self.map_id = map_id if map_id in gd.maps else next(iter(gd.maps))
        self.x = self.y = 0
        self.ox = self.oy = 0
        self.brush: dict[str, int] = {}         # タイルセットごとの選択中のタイル
        self.pen = False
        self.show_objects = True
        self.mode = "edit"                      # edit | maps | quit | help
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
        stack = self.undo[self.map_id]
        stack.append((self.x, self.y, old))
        del stack[:-UNDO_LIMIT]
        self.dirty.add(self.map_id)

    def undo_last(self) -> None:
        stack = self.undo[self.map_id]
        if not stack:
            self.say("元に戻す操作はありません")
            return
        x, y, old = stack.pop()
        rows = self.rows[self.map_id]
        rows[y] = rows[y][:x] + old + rows[y][x + 1:]
        self.x, self.y = x, y
        if rows == self.map.rows:
            self.dirty.discard(self.map_id)
        else:
            self.dirty.add(self.map_id)

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

    def save(self) -> bool:
        if not self.dirty:
            self.say("変更はありません")
            return True
        path = self.root / MAP_FILE
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            out = text
            for mid in sorted(self.dirty):
                out = replace_rows(out, mid, self.rows[mid])
        except (OSError, UnicodeDecodeError, MapFileError) as e:
            self.say(f"保存できません：{e}", ERR)
            return False
        if not self.backed_up:
            (self.root / (MAP_FILE + ".bak")).write_bytes(raw)
            self.backed_up = True
        data = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + out.encode("utf-8")
        tmp = path.with_name(MAP_FILE + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        for mid in self.dirty:
            self.gd.maps[mid].rows = list(self.rows[mid])
        saved = len(self.dirty)
        self.dirty.clear()
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

    def _key_maps(self, ev: KeyEvent, c: str) -> None:
        ids = list(self.gd.maps)
        if c == "UP":
            self.list_i = (self.list_i - 1) % len(ids)
        elif c == "DOWN":
            self.list_i = (self.list_i + 1) % len(ids)
        elif c in ("ENTER", " "):
            self.open_map(ids[self.list_i])
            self.mode = "edit"
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
        for ty in range(min(rows, self.height - oy)):
            for tx in range(min(cols, self.width - ox)):
                mx, my = ox + tx, oy + ty
                glyph, st = self._cell(grid, mx, my)
                if mx == self.x and my == self.y:
                    st = st._replace(attrs=st.attrs | 8)       # 反転表示
                buf.put(px + tx * 2, py + ty, glyph, st, clip=area)

    def _cell(self, grid: list[str], x: int, y: int) -> tuple[str, Style]:
        if self.show_objects:
            m = self.map
            for n in m.npcs:
                if (n.x, n.y) == (x, y):
                    return n.glyph, Style.of(n.color or "white", bold=True)
            for w in m.warps:
                if (w.x, w.y) == (x, y):
                    return WARP_GLYPH, Style.of("bright_magenta", bold=True)
            for e in m.events:
                if (e.x, e.y) == (x, y):
                    return EVENT_GLYPH, Style.of("bright_cyan", bold=True)
        tile = self.tile_at(x, y)
        if tile is None:
            return UNKNOWN_GLYPH, Style.of("bright_red")
        return tile.glyph, Style.of(tile.color) if tile.color else Style()

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
            m = self.map
            for n in m.npcs:
                if (n.x, n.y) == (self.x, self.y):
                    out.append((f"NPC {n.id}（{n.move}）", TEXT))
            for w in m.warps:
                if (w.x, w.y) == (self.x, self.y):
                    out.append((f"ワープ → {w.to} ({w.tx}, {w.ty})", TEXT))
            for e in m.events:
                if (e.x, e.y) == (self.x, self.y):
                    out.append((f"イベント {e.label}（{e.trigger}）", TEXT))
        out.append((f"ペン {'オン' if self.pen else 'オフ'}　表示 {'オン' if self.show_objects else 'オフ'}", DIM))
        out.append(("? で操作説明", DIM))
        return out

    def _draw_status(self, buf: Buffer, y: int, w: int) -> None:
        if self.message:
            buf.put(1, y, truncate(self.message, w - 2), self.message_style)
        else:
            changed = f"　未保存 {len(self.dirty)} マップ" if self.dirty else ""
            buf.put(1, y, truncate("矢印：移動  Enter：塗る  [ ]：タイル  i：スポイト  p：ペン  u：戻す  "
                                   "m：マップ  s：保存  q：終了" + changed, w - 2), DIM)

    def _overlay(self, buf: Buffer, w: int, h: int, title: str) -> Rect:
        rect = Rect(max(0, (buf.width - w) // 2), max(0, (buf.height - h) // 2), min(w, buf.width), min(h, buf.height))
        return buf.box(rect, Style.of("bright_white"), title=title, title_style=TITLE)

    def _draw_map_list(self, buf: Buffer) -> None:
        ids = list(self.gd.maps)
        h = min(len(ids) + 2, buf.height - 4)
        inner = self._overlay(buf, 60, h, "マップ（Enter で開く / Esc で戻る）")
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
