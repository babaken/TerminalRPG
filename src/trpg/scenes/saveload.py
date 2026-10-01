"""セーブ／ロード画面（3 スロット）。

- mode="save": フィールドのメニュー・セーブポイント（@save_point）から。上書きは確認する。
- mode="load": タイトルの「つづきから」から。読み込めないスロットは選べない。
フィールドから開いたときはフィールドの上に重ねて描く。閉じると ``closed`` が立つ（@save_point の再開用）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from ..app import Scene
from ..save import SLOTS, SaveError, SaveStore, SlotInfo
from ..term import Action, Buffer, KeyEvent, Rect, Style, truncate
from ..term.buffer import BOX_SINGLE
from ..ui.widgets import CURSOR, DIM_TEXT, FRAME, TEXT, ChoiceWindow, MessageWindow
from ..world.state import GameState, format_text

if TYPE_CHECKING:
    from ..game import Game
    from .field import FieldScene


class SaveLoadScene(Scene):
    def __init__(self, game: "Game", mode: str, *, field: Optional["FieldScene"] = None,
                 on_load: Optional[Callable[[GameState], None]] = None):
        self.game = game
        self.mode = mode
        self.field = field
        self.on_load = on_load
        self.store: SaveStore = game.saves()
        self.infos: list[SlotInfo] = self.store.infos()
        self.index = 0
        if mode == "save":   # 最初は最後にセーブしたスロット、なければ空きスロット
            latest = self.store.latest()
            empty = next((i.slot for i in self.infos if not i.exists), None)
            self.index = (latest or empty or 1) - 1
        else:
            latest = self.store.latest()
            self.index = (latest or 1) - 1
        self.closed = False
        self.msg = MessageWindow()
        self.choice: Optional[ChoiceWindow] = None
        self._choice_cb: Optional[Callable[[int], None]] = None
        self._after_msg: Optional[Callable[[], None]] = None

    # ---------------------------------------------------------------- 補助
    def say(self, text: str, then: Optional[Callable[[], None]] = None) -> None:
        self.msg.open([("", text)])
        self._after_msg = then

    def ask(self, text: str, options: list[str], cb: Callable[[int], None]) -> None:
        self.msg.open([("", text)])
        self.msg.shown = 10 ** 6
        self.choice = ChoiceWindow(options, cancel_index=len(options) - 1)
        self._choice_cb = cb

    def close(self) -> None:
        self.closed = True
        self.app.pop()

    # ---------------------------------------------------------------- 入力
    def update(self, dt: float) -> None:
        self.msg.update(dt)

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.choice is not None:
            if Action.UP in actions:
                self.choice.move(-1)
            elif Action.DOWN in actions:
                self.choice.move(1)
            elif Action.OK in actions or Action.CANCEL in actions:
                idx = self.choice.index if Action.OK in actions else self.choice.cancel_index
                cb, self._choice_cb = self._choice_cb, None
                self.choice = None
                self.msg.close()
                if cb:
                    cb(idx)
            return
        if self.msg.active:
            if Action.OK in actions or Action.CANCEL in actions:
                if self.msg.advance():
                    self.msg.close()
                    cb, self._after_msg = self._after_msg, None
                    if cb:
                        cb()
            return
        if Action.UP in actions:
            self.index = (self.index - 1) % SLOTS
        elif Action.DOWN in actions:
            self.index = (self.index + 1) % SLOTS
        elif Action.CANCEL in actions:
            self.close()
        elif Action.OK in actions:
            self._select(self.infos[self.index])

    def _select(self, info: SlotInfo) -> None:
        if self.mode == "save":
            if info.exists:
                self.ask(f"スロット {info.slot} に上書きしますか？", ["はい", "いいえ"],
                         lambda i: self._do_save(info.slot) if i == 0 else None)
            else:
                self._do_save(info.slot)
            return
        if not info.exists:
            return
        if not info.ok:
            self.say(info.error)
            return
        self.ask(f"スロット {info.slot} のデータで再開しますか？", ["はい", "いいえ"],
                 lambda i: self._do_load(info.slot) if i == 0 else None)

    def _do_save(self, slot: int) -> None:
        st = self.field.st
        map_name = ""
        if self.field.map is not None:
            map_name = format_text(self.field.map.name, st, self.game.data)
        try:
            self.store.save(slot, st, map_name)
        except SaveError as e:
            self.say(f"セーブできませんでした。{e}")
            return
        self.infos = self.store.infos()
        self.say(f"スロット {slot} にセーブしました。", then=self.close)

    def _do_load(self, slot: int) -> None:
        try:
            st = self.store.load(slot)
        except SaveError as e:
            self.say(str(e))
            return
        if self.on_load:
            self.on_load(st)

    # ---------------------------------------------------------------- 描画
    def draw(self, buf: Buffer) -> None:
        msg_h = 5
        if self.field is not None:
            self.field.draw(buf, overlay=True)
            buf.fill(Rect(0, 0, buf.width, buf.height - msg_h), " ")
        w = min(88, buf.width - 4)
        h = SLOTS * 3 + 3
        rect = Rect((buf.width - w) // 2, max(1, (buf.height - msg_h - h) // 2), w, h)
        title = "セーブ" if self.mode == "save" else "つづきから"
        inner = buf.box(rect, FRAME, title=title, chars=BOX_SINGLE)
        for i, info in enumerate(self.infos):
            sel = i == self.index
            y = inner.y + i * 3
            disabled = self.mode == "load" and not (info.exists and info.ok)
            st = CURSOR if sel else (DIM_TEXT if disabled else TEXT)
            buf.put(inner.x + 1, y, ("▶ " if sel else "  ") + f"スロット {info.slot}", st, clip=inner)
            line = info.label()
            if info.exists and info.ok and info.chapter_title:
                line = line.replace(f"第{info.chapter}章", f"第{info.chapter}章「{info.chapter_title}」")
            lst = Style.of("bright_red") if info.exists and not info.ok else (DIM_TEXT if not info.exists else TEXT)
            buf.put(inner.x + 4, y + 1, truncate(line, inner.w - 6), lst, clip=inner)
        hint = "Enter: 決定  Esc: もどる"
        buf.put(inner.right - len(hint) - 8, inner.bottom, hint, DIM_TEXT)
        mrect = Rect(0, buf.height - msg_h, buf.width, msg_h)
        if self.msg.active:
            self.msg.draw(buf, mrect, show_cursor=self.choice is None)
        else:
            buf.box(mrect, FRAME, chars=BOX_SINGLE)
        if self.choice is not None:
            self.choice.draw(buf, buf.width - 1, buf.height - msg_h + 1)
