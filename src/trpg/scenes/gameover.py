"""全滅したときの画面（要件 F-65：セーブから / タイトルへ / 選択、はシナリオで設定）。"""
from __future__ import annotations

from ..app import Scene
from ..term import Action, Buffer, KeyEvent, Style
from ..ui.widgets import CURSOR, DIM_TEXT, TEXT

FADE_IN = 1.2


class GameOverScene(Scene):
    def __init__(self, game, mode: str):
        self.game = game
        self.mode = mode if mode in ("retry_from_save", "title", "choose") else "choose"
        self.t = 0.0
        self.index = 0
        self.notice = ""
        if self.mode == "retry_from_save":
            self.options = ["セーブからやり直す"]
        elif self.mode == "title":
            self.options = ["タイトルへもどる"]
        else:
            self.options = ["セーブからやり直す", "タイトルへもどる"]

    def update(self, dt: float) -> None:
        self.t += dt

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.t < FADE_IN:
            return
        if Action.UP in actions:
            self.index = (self.index - 1) % len(self.options)
        elif Action.DOWN in actions:
            self.index = (self.index + 1) % len(self.options)
        elif Action.OK in actions:
            if self.options[self.index] == "セーブからやり直す":
                # セーブ機能は未実装。実装後はここで最後のセーブを読み込む
                if not self.notice:
                    self.notice = "セーブデータがありません（セーブ機能は未実装です）。Enter でタイトルへ"
                    return
            self._to_title()

    def _to_title(self) -> None:
        from .title import TitleScene
        while len(self.app._stack) > 1:
            self.app.pop()
        self.app.replace(TitleScene(self.game))

    def draw(self, buf: Buffer) -> None:
        y = buf.height // 2 - 3
        level = min(1.0, self.t / FADE_IN)
        st = Style.of("bright_red", bold=True) if level >= 0.6 else Style.of("red")
        if level > 0.2:
            buf.put_center(y, "全滅してしまった……", st)
        if self.t < FADE_IN:
            return
        for i, opt in enumerate(self.options):
            sel = i == self.index
            buf.put_center(y + 3 + i * 2, ("▶ " if sel else "  ") + opt, CURSOR if sel else TEXT)
        if self.notice:
            buf.put_center(y + 4 + len(self.options) * 2, self.notice, DIM_TEXT)
