"""タイトル画面・名前入力・シナリオ選択。"""
from __future__ import annotations

from ..i18n import get_lang, lang_label, save_lang, set_lang, tr

from pathlib import Path
from typing import Callable, Optional

from ..app import Scene
from ..data import DataError
from ..game import Game, load_game
from ..package import Candidate, PackageError
from ..term import Action, Buffer, Key, KeyEvent, Rect, Style, text_width, truncate, wrap
from ..term.buffer import BOX_SINGLE
from ..ui.aa import draw_aa
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
        if game.package.has_translations() and game.package.lang != get_lang():
            self._reload_game()                     # ゲーム中に言語を変えてタイトルに戻ったとき
        try:
            has_save = self.game.saves().any_save()
        except Exception:
            has_save = False
        self.has_save = has_save
        self._make_items()
        # 背景エフェクト（manifest の title_screen.effect）
        m = self.game.manifest
        self.bg_kind = m.title_effect if m.title_effect not in ("", "none") else ""
        self.bg = None
        self._make_bg()
        if has_save:
            self.index = 1

    LANG_INDEX = 2                     # はじめから / つづきから / 言語 / おわる

    def _make_items(self) -> None:
        self.items = [(tr('はじめから'), True), (tr('つづきから'), self.has_save), (lang_label(), True),
                      (tr('おわる'), True)]

    def toggle_lang(self) -> None:
        """日本語 ⇄ 英語を切り替えて設定ファイルに覚える。"""
        set_lang("en" if get_lang() == "ja" else "ja")
        save_lang(get_lang())
        self._make_items()
        if self.game.package.has_translations():
            self._reload_game()

    def _reload_game(self) -> None:
        """シナリオに言語別の本文（lang/<言語>/）があれば、選んだ言語で読み直す。"""
        old = self.game
        try:
            new = load_game(old.package.path, dev=old.dev)
        except (PackageError, DataError):
            self.notice = tr('この言語のシナリオの文に誤りがあります。--check で確認してください')
            return
        new.save_dir = old.save_dir
        old.close()
        self.game = new

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
                if self.items[1][1]:
                    from .saveload import SaveLoadScene
                    self.app.push(SaveLoadScene(self.game, "load",
                                                on_load=lambda st: start_field(self.app, self.game, st)))
                else:
                    self.notice = tr('セーブデータがありません')
            elif self.index == self.LANG_INDEX:
                self.toggle_lang()
            else:
                self.app.quit()
        elif Action.CANCEL in actions:
            self.index = len(self.items) - 1

    def debug_state(self) -> str:
        return f"index={self.index} notice={self.notice!r}"

    def _make_bg(self) -> None:
        from ..effects import Starfall, Weather
        if self.bg_kind == "starfall":
            self.bg = Starfall(count=5, ms=3000)
        elif self.bg_kind in ("rain", "snow"):
            self.bg = Weather(self.bg_kind, 1)

    def update(self, dt: float) -> None:
        if self.bg is None:
            return
        self.bg.update(dt)
        if getattr(self.bg, "done", False):        # 流れ星は終わったら次の流れ星を降らせる
            self._make_bg()

    def new_game(self) -> None:
        m = self.game.manifest
        hero = self.game.data.characters[m.start_party[0]]
        if hero.name_input:
            self.app.push(NameInputScene(hero.name, self.start))
        else:
            self.start(hero.name)

    def start(self, name: str) -> None:
        state = GameState.new_game(self.game.data, self.game.manifest, name)
        start_field(self.app, self.game, state, new_game=True)

    def draw(self, buf: Buffer) -> None:
        if self.bg is not None:                     # 背景を先に描き、タイトルと選択肢を上に重ねる
            if self.bg_kind == "starfall":
                self.bg.apply(buf)
            else:
                self.bg.apply(buf, buf.rect)
        m = self.game.manifest
        aa = self.game.data.aa.get(m.title_aa) if m.title_aa else None
        top = max(1, buf.height // 2 - 10)
        if aa:
            w = max(text_width(l) for l in aa)
            draw_aa(buf, (buf.width - w) // 2, top, aa, Style.of("bright_yellow", bold=True),
                    self.game.data.aa_color.get(m.title_aa), transparent=False)
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


def start_field(app, game: Game, state: GameState, new_game: bool = False) -> None:
    """画面を全部片付けてフィールドを始める（ニューゲーム・ロード共通）。"""
    from .field import FieldScene
    field = FieldScene(game, state)
    while len(app._stack) > 1:
        app.pop()
    app.replace(field)
    if new_game:
        field.start_script(game.manifest.start_label)
        return
    # ロード：マップに入ったときの自動イベントは起こさない。*on_load があれば実行する
    field.pending_auto = False
    if field.vm.has_label("on_load"):
        field.start_script("on_load")


class NameInputScene(Scene):
    accepts_text = True

    def __init__(self, default: str, on_done: Callable[[str], None], prompt: str = "",
                 on_cancel: Optional[Callable[[], None]] = None):
        self.name = default
        self.default = default
        self.on_done = on_done
        self.prompt = prompt                   # 空なら「主人公の名前を入力してください」
        self.on_cancel = on_cancel             # None なら Esc で前の画面へ戻る（主人公）
        self.warn = ""

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        self.warn = ""
        if ev.key is Key.ENTER:
            name = self.name.strip()
            if not name:
                self.warn = tr('名前を入力してください')
                return
            self.on_done(name)
        elif ev.key is Key.ESC:
            if self.on_cancel is not None:
                self.on_cancel()
            else:
                self.app.pop()
        elif ev.key is Key.BACKSPACE:
            self.name = self.name[:-1]
        elif ev.key is Key.CHAR:
            if text_width(self.name + ev.char) > NAME_MAX_WIDTH:
                self.warn = tr('これ以上入力できません')
            elif ev.char.isprintable():
                self.name += ev.char

    def debug_state(self) -> str:
        return f"name={self.name!r} warn={self.warn!r}"

    def draw(self, buf: Buffer) -> None:
        w, h = 64, 11
        rect = Rect((buf.width - w) // 2, (buf.height - h) // 2, w, h)
        inner = buf.box(rect, FRAME, title=tr('なまえ'), chars=BOX_SINGLE)
        buf.put(inner.x + 2, inner.y + 1, self.prompt or tr('主人公の名前を入力してください'), TEXT)
        field = Style.of("bright_white", bold=True)
        end_x = buf.put(inner.x + 4, inner.y + 3, tr('［ ') + self.name, field)
        buf.put(inner.x + 4 + 2 + NAME_MAX_WIDTH + 2, inner.y + 3, tr('］'), field)
        # 端末カーソルを入力位置に出す → 日本語入力の変換中の文字がここに表示される
        buf.cursor = (end_x, inner.y + 3)
        buf.put(inner.x + 2, inner.y + 5, tr('Enter: 決定  BackSpace: 削除  Esc: 戻る') if self.on_cancel is None
                else tr('Enter: 決定  BackSpace: 削除  Esc: 元の名前（{0}）のまま', self.default), DIM_TEXT)
        buf.put(inner.x + 2, inner.y + 6, tr('日本語は Enter で変換を確定してから、もう一度 Enter'), Style.of("cyan"))
        buf.put(inner.x + 2, inner.y + 7, tr('決定したら［半角/全角］で日本語入力をオフにしてください'), Style.of("cyan"))
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
                self.error = tr('データに {0} 件のエラーがあります。python -m trpg --check {1} で確認してください', len(e.report.errors), c.path)
                return
            self.app.replace(TitleScene(game))
        elif Action.CANCEL in actions:
            self.app.quit()

    def draw(self, buf: Buffer) -> None:
        buf.put_center(2, tr('シナリオを選んでください'), Style.of("bright_yellow", bold=True))
        for i, c in enumerate(self.cands):
            sel = i == self.index
            label = f"{c.title or c.path.name}  {c.version}"
            st = CURSOR if sel else (DIM_TEXT if c.error else TEXT)
            buf.put(6, 5 + i, ("▶ " if sel else "  ") + truncate(label, buf.width - 12), st)
            if c.error:
                buf.put(buf.width - 14, 5 + i, tr('（読込不可）'), DIM_TEXT)
        if self.error:
            y = 6 + len(self.cands)
            for line in wrap(self.error, buf.width - 12)[: buf.height - y - 2]:
                buf.put(6, y, line, Style.of("bright_red"))
                y += 1
        buf.put_center(buf.height - 2, tr('Enter: 決定  Esc: 終了'), DIM_TEXT)
