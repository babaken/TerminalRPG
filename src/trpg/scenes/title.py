"""タイトル画面・名前入力・シナリオ選択。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from ..app import Scene
from ..data import DataError
from ..game import Game, load_game
from ..package import Candidate, PackageError
from ..term import Action, Buffer, Key, KeyEvent, Rect, Style, text_width, truncate, wrap
from ..term.buffer import BOX_SINGLE
from ..ui.widgets import CURSOR, DIM_TEXT, FRAME, TEXT
from ..world.state import GameState

NAME_MAX_WIDTH = 12   # 全角 6 文字


def _menu(buf: Buffer, items: list[tuple[str, bool]], index: int, top: int) -> None:
    w = max(text_width(t) for t, _ in items) + 4
    x = (buf.width - w) // 2
    for i, (label, enabled) in enumerate(items):
        sel = i == index
        st = CURSOR if sel else (TEXT if enabled else DIM_TEXT)
        buf.put(x, top + i * 2, ("▶ " if sel else "  ") + label, st)


class TitleScene(Scene):
    def __init__(self, game: Game):
        self.game = game
        self.index = 0
        self.notice = ""
        self.items = [("はじめから", True), ("つづきから", False), ("おわる", True)]

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        self.notice = ""
        if Action.UP in actions:
            self.index = (self.index - 1) % len(self.items)
        elif Action.DOWN in actions:
            self.index = (self.index + 1) % len(self.items)
        elif Action.OK in actions:
            if self.index == 0:
                self.new_game()
            elif self.index == 1:
                self.notice = "セーブ・ロードは未実装です"
            else:
                self.app.quit()
        elif Action.CANCEL in actions:
            self.index = len(self.items) - 1

    def debug_state(self) -> str:
        return f"index={self.index} notice={self.notice!r}"

    def new_game(self) -> None:
        m = self.game.manifest
        hero = self.game.data.characters[m.start_party[0]]
        if hero.name_input:
            self.app.push(NameInputScene(hero.name, self.start))
        else:
            self.start(hero.name)

    def start(self, name: str) -> None:
        from .field import FieldScene
        state = GameState.new_game(self.game.data, self.game.manifest, name)
        field = FieldScene(self.game, state)
        # 名前入力から来た場合はスタックを全部入れ替える
        while len(self.app._stack) > 1:
            self.app.pop()
        self.app.replace(field)
        field.start_script(self.game.manifest.start_label)

    def draw(self, buf: Buffer) -> None:
        m = self.game.manifest
        aa = self.game.data.aa.get(m.title_aa) if m.title_aa else None
        top = max(1, buf.height // 2 - 10)
        if aa:
            w = max(text_width(l) for l in aa)
            buf.put_lines((buf.width - w) // 2, top, aa, Style.of("bright_yellow", bold=True))
            y = top + len(aa) + 2
        else:
            buf.put_center(top + 2, m.title, Style.of("bright_yellow", bold=True))
            y = top + 5
        buf.put_center(y, m.title + (f"  ver {m.version}" if m.version else ""), Style.of("gray"))
        _menu(buf, self.items, self.index, y + 3)
        if self.notice:
            buf.put_center(y + 3 + len(self.items) * 2 + 1, self.notice, Style.of("yellow"))
        foot = f"{m.author}" if m.author else ""
        if foot:
            buf.put_center(buf.height - 2, foot, Style.of("gray"))


class NameInputScene(Scene):
    accepts_text = True

    def __init__(self, default: str, on_done: Callable[[str], None]):
        self.name = default
        self.on_done = on_done
        self.warn = ""

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        self.warn = ""
        if ev.key is Key.ENTER:
            name = self.name.strip()
            if not name:
                self.warn = "名前を入力してください"
                return
            self.on_done(name)
        elif ev.key is Key.ESC:
            self.app.pop()
        elif ev.key is Key.BACKSPACE:
            self.name = self.name[:-1]
        elif ev.key is Key.CHAR:
            if text_width(self.name + ev.char) > NAME_MAX_WIDTH:
                self.warn = "これ以上入力できません"
            elif ev.char.isprintable():
                self.name += ev.char

    def debug_state(self) -> str:
        return f"name={self.name!r} warn={self.warn!r}"

    def draw(self, buf: Buffer) -> None:
        w, h = 64, 11
        rect = Rect((buf.width - w) // 2, (buf.height - h) // 2, w, h)
        inner = buf.box(rect, FRAME, title="なまえ", chars=BOX_SINGLE)
        buf.put(inner.x + 2, inner.y + 1, "主人公の名前を入力してください", TEXT)
        field = Style.of("bright_white", bold=True)
        end_x = buf.put(inner.x + 4, inner.y + 3, "［ " + self.name, field)
        buf.put(inner.x + 4 + 2 + NAME_MAX_WIDTH + 2, inner.y + 3, "］", field)
        # 端末カーソルを入力位置に出す → 日本語入力の変換中の文字がここに表示される
        buf.cursor = (end_x, inner.y + 3)
        buf.put(inner.x + 2, inner.y + 5, "Enter: 決定  BackSpace: 削除  Esc: 戻る", DIM_TEXT)
        buf.put(inner.x + 2, inner.y + 6, "日本語は Enter で変換を確定してから、もう一度 Enter", Style.of("cyan"))
        buf.put(inner.x + 2, inner.y + 7, "決定したら［半角/全角］で日本語入力をオフにしてください", Style.of("cyan"))
        if self.warn:
            buf.put(inner.x + 2, inner.y + 8, self.warn, Style.of("yellow"))


class SelectScene(Scene):
    """起動時に複数のシナリオが見つかったときの選択画面。"""

    def __init__(self, candidates: list[Candidate], dev: bool = False):
        self.cands = candidates
        self.index = 0
        self.dev = dev
        self.error = ""

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if Action.UP in actions:
            self.index = (self.index - 1) % len(self.cands)
            self.error = ""
        elif Action.DOWN in actions:
            self.index = (self.index + 1) % len(self.cands)
            self.error = ""
        elif Action.OK in actions:
            c = self.cands[self.index]
            if c.error:
                self.error = c.error
                return
            try:
                game = load_game(c.path, dev=self.dev)
            except PackageError as e:
                self.error = str(e)
                return
            except DataError as e:
                self.error = f"データに {len(e.report.errors)} 件のエラーがあります。python -m trpg --check {c.path} で確認してください"
                return
            self.app.replace(TitleScene(game))
        elif Action.CANCEL in actions:
            self.app.quit()

    def draw(self, buf: Buffer) -> None:
        buf.put_center(2, "シナリオを選んでください", Style.of("bright_yellow", bold=True))
        for i, c in enumerate(self.cands):
            sel = i == self.index
            label = f"{c.title or c.path.name}  {c.version}"
            st = CURSOR if sel else (DIM_TEXT if c.error else TEXT)
            buf.put(6, 5 + i, ("▶ " if sel else "  ") + truncate(label, buf.width - 12), st)
            if c.error:
                buf.put(buf.width - 14, 5 + i, "（読込不可）", DIM_TEXT)
        if self.error:
            y = 6 + len(self.cands)
            for line in wrap(self.error, buf.width - 12)[: buf.height - y - 2]:
                buf.put(6, y, line, Style.of("bright_red"))
                y += 1
        buf.put_center(buf.height - 2, "Enter: 決定  Esc: 終了", DIM_TEXT)
