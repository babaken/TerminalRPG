"""端末レイヤの動作確認用デモ。基本設計 2.1 のフィールド画面レイアウトを再現する。

操作: 移動=矢印/WASD/テンキー  決定=Enter/Z  F=フラッシュ  T=色調切替  B=枠線切替  Q/Esc=終了
"""
from __future__ import annotations

from ..app import Scene
from ..term import (BOX_ASCII, BOX_SINGLE, Action, Buffer, Key, KeyEvent, Rect, Style,
                    pad, wrap)
from ..term.width import get_ambiguous_width

MAP_ROWS = [
    "########################################",
    "#....T....~~~~.........T.............T.#",
    "#..T......~~~~....H...........TT.......#",
    "#.........~~~~.................T.......#",
    "#....TT...~~~~......................T..#",
    "#.........~~~~~~~~~~~~...........H.....#",
    "#..........................T...........#",
    "#...T.................................>#",
    "#.........H.......T.........~~~~.......#",
    "#..............................~~~~....#",
    "#....T.........................~~~~....#",
    "#...........T.....H....................#",
    "#..TT..............................T...#",
    "#.................~~~~.................#",
    "#........T........~~~~.......H.........#",
    "#.......................T..............#",
    "#..H...........T.......................#",
    "#...........................T......T...#",
    "#.....T..............H.................#",
    "########################################",
]

# 1 タイル = 2 セル。曖昧幅を避けて全角文字（F/W）を使う
TILES = {
    "#": ("＃", Style.of("gray"), False),
    ".": ("．", Style.of("green"), True),
    "T": ("木", Style.of("bright_green"), False),
    "~": ("～", Style.of("bright_blue"), False),
    "H": ("家", Style.of("yellow"), False),
    ">": ("▼", Style.of("bright_yellow"), True),  # ▼ は曖昧幅 → 幅 1 のとき空白を足す
}

MESSAGES = [
    "母「おかえり。森は楽しかった？」",
    "カイ「おーいユウ！　今日こそ森の奥まで行ってみようぜ！」",
    "これは描画と入力のデモです。全角と半角の混在（ABC あいう ｱｲｳ 123）も正しく表示されるか確認してください。",
]

TINTS = ["none", "night", "sepia", "red"]


_TINT_FG = {"night": 4, "sepia": 3, "red": 1}


def _tint(name: str):
    """色調変更（基本設計 11 章 tint の試作）。前景色を 1 色に寄せる。"""
    fg = _TINT_FG.get(name)
    if fg is None:
        return None
    return lambda st: st._replace(fg=fg)


class TermDemoScene(Scene):
    PANEL_W = 34
    MSG_H = 5

    def __init__(self):
        self.px, self.py = 5, 5
        self.msg_index = 0
        self.msg_chars = 0.0
        self.flash_time = 0.0
        self.tint_index = 0
        self.box_chars = BOX_SINGLE
        self.last_key = "-"
        self.frames = 0
        self.fps = 0.0
        self._fps_acc = 0.0
        self._fps_n = 0

    # ---------------------------------------------------------------- 入力
    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        self.last_key = str(ev)
        if ev.key is Key.ESC or (ev.key is Key.CHAR and ev.char.lower() == "q"):
            self.app.quit()
            return
        dx = dy = 0
        if Action.UP in actions:
            dy = -1
        elif Action.DOWN in actions:
            dy = 1
        elif Action.LEFT in actions:
            dx = -1
        elif Action.RIGHT in actions:
            dx = 1
        if dx or dy:
            nx, ny = self.px + dx, self.py + dy
            if TILES[MAP_ROWS[ny][nx]][2]:
                self.px, self.py = nx, ny
            return
        if Action.OK in actions:
            text = MESSAGES[self.msg_index]
            if self.msg_chars < len(text):
                self.msg_chars = len(text)  # 表示途中ならスキップ
            else:
                self.msg_index = (self.msg_index + 1) % len(MESSAGES)
                self.msg_chars = 0
            return
        if ev.key is Key.CHAR:
            c = ev.char.lower()
            if c == "f":
                self.flash_time = 0.15
            elif c == "t":
                self.tint_index = (self.tint_index + 1) % len(TINTS)
            elif c == "b":
                self.box_chars = BOX_ASCII if self.box_chars == BOX_SINGLE else BOX_SINGLE

    # ---------------------------------------------------------------- 更新
    def update(self, dt: float) -> None:
        self.frames += 1
        self.msg_chars += dt * 30  # 1 秒 30 文字
        self.flash_time = max(0.0, self.flash_time - dt)
        self._fps_acc += dt
        self._fps_n += 1
        if self._fps_acc >= 0.5:
            self.fps = self._fps_n / self._fps_acc
            self._fps_acc = 0.0
            self._fps_n = 0

    # ---------------------------------------------------------------- 描画
    def draw(self, buf: Buffer) -> None:
        if self.flash_time > 0:
            buf.fill(buf.rect, " ", Style.of(bg="bright_white"))
            return
        W, H = buf.width, buf.height
        frame = Style.of("white")
        map_rect = Rect(0, 0, W - self.PANEL_W, H - self.MSG_H)
        panel_rect = Rect(W - self.PANEL_W, 0, self.PANEL_W, H - self.MSG_H)
        msg_rect = Rect(0, H - self.MSG_H, W, self.MSG_H)

        inner = buf.box(map_rect, frame, title="ハジマリ村", chars=self.box_chars)
        self._draw_map(buf, inner)
        inner = buf.box(panel_rect, frame, title="パーティ", chars=self.box_chars)
        self._draw_panel(buf, inner)
        inner = buf.box(msg_rect, frame, chars=self.box_chars)
        self._draw_message(buf, inner)

        fn = _tint(TINTS[self.tint_index])
        if fn:
            buf.map_styles(fn)

    def _draw_map(self, buf: Buffer, area: Rect) -> None:
        cols = area.w // 2
        rows = area.h
        mh, mw = len(MAP_ROWS), len(MAP_ROWS[0])
        ox = min(max(0, self.px - cols // 2), max(0, mw - cols))
        oy = min(max(0, self.py - rows // 2), max(0, mh - rows))
        for ty in range(rows):
            my = oy + ty
            if my >= mh:
                break
            for tx in range(cols):
                mx = ox + tx
                if mx >= mw:
                    break
                x, y = area.x + tx * 2, area.y + ty
                if (mx, my) == (self.px, self.py):
                    buf.put(x, y, "＠", Style.of("bright_white", bold=True), clip=area)
                    continue
                glyph, st, _ = TILES[MAP_ROWS[my][mx]]
                if get_ambiguous_width() == 1 and glyph == "▼":
                    glyph = "▼ "
                buf.put(x, y, glyph, st, clip=area)

    def _draw_panel(self, buf: Buffer, area: Rect) -> None:
        y = area.y
        party = [("ユウ", "勇者", 3, 32, 40, 8, 10), ("リナ", "僧侶", 3, 25, 25, 18, 20)]
        for name, job, lv, hp, mhp, mp, mmp in party:
            buf.put(area.x + 1, y, f"{pad(name, 8)}{pad(job, 6)}Lv {lv:>2}", Style.of("bright_white", bold=True), clip=area)
            hp_style = Style.of("bright_red") if hp * 4 < mhp else Style.of("white")
            buf.put(area.x + 2, y + 1, f"HP {hp:>3}/{mhp:>3}  MP {mp:>3}/{mmp:>3}", hp_style, clip=area)
            y += 3
        buf.put(area.x + 1, y, "G    120", Style.of("yellow"), clip=area)
        y += 2
        info = [
            f"端末   {buf.width} × {buf.height}",
            f"FPS    {self.fps:5.1f}",
            f"出力   {self.app.terminal.screen.bytes_written if self.app.terminal else 0:>5} 文字/frame",
            f"最終キー {self.last_key}",
            f"位置   ({self.px}, {self.py})",
            f"色調   {TINTS[self.tint_index]}",
            f"曖昧幅 {get_ambiguous_width()}",
        ]
        for line in info:
            if y >= area.bottom:
                break
            buf.put(area.x + 1, y, line, Style.of("gray"), clip=area)
            y += 1
        help_lines = ["F:発光 T:色調 B:枠線", "Enter:会話送り Q:終了"]
        hy = area.bottom - len(help_lines)
        for i, line in enumerate(help_lines):
            if hy + i > y:
                buf.put(area.x + 1, hy + i, line, Style.of("cyan"), clip=area)

    def _draw_message(self, buf: Buffer, area: Rect) -> None:
        text = MESSAGES[self.msg_index][: int(self.msg_chars)]
        lines = wrap(text, area.w - 2)
        for i, line in enumerate(lines[: area.h]):
            buf.put(area.x + 1, area.y + i, line, Style.of("bright_white"), clip=area)
        if self.msg_chars >= len(MESSAGES[self.msg_index]) and (self.frames // 10) % 2 == 0:
            buf.put(area.right - 3, area.bottom - 1, "▼", Style.of("yellow", bold=True), clip=area)
