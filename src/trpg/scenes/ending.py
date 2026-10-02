"""エンディング画面（@ending）：タイトル・おわりの言葉・パーティ・プレイ時間を出し、Enter でタイトルへ。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..app import Scene
from ..term import Action, Buffer, KeyEvent, Style, truncate
from ..world.state import format_text

if TYPE_CHECKING:
    from .field import FieldScene

FADE_SECONDS = 1.5
READY_SECONDS = 1.0           # これより前のキーは受け付けない（会話の送りすぎで飛ばさないように）


class EndingScene(Scene):
    def __init__(self, field: "FieldScene", text: str = ""):
        self.field = field
        self.text = text or "―― おわり ――"
        self.t = 0.0
        self.closed = False

    def on_key(self, ev: KeyEvent, actions: frozenset[Action]) -> None:
        if self.t >= READY_SECONDS and (Action.OK in actions or Action.CANCEL in actions):
            self.closed = True
            self.app.pop()

    def update(self, dt: float) -> None:
        self.t += dt

    def lines(self) -> list[tuple[str, Style]]:
        st = self.field.st
        gd = self.field.gd
        t = int(st.playtime)
        party = "　".join(f"{m.name} Lv{m.lv}" for m in st.party)
        out = [
            (self.field.game.manifest.title, Style.of("bright_white", bold=True)),
            ("", Style()),
            (format_text(self.text, st, gd), Style.of("bright_yellow")),
            ("", Style()),
            (party, Style.of("white")),
            (f"プレイ時間 {t // 3600:02}:{t // 60 % 60:02}:{t % 60:02}", Style.of("white")),
            ("", Style()),
            ("遊んでくれて、ありがとう。", Style.of("bright_white")),
        ]
        if self.t >= READY_SECONDS:
            out += [("", Style()), ("Enter でタイトルへ", Style.of("gray"))]
        return out

    def draw(self, buf: Buffer) -> None:
        buf.fill(buf.rect, " ", Style(bg=0))
        if self.t < FADE_SECONDS * 0.3:
            return
        lines = self.lines()
        top = max(0, (buf.height - len(lines)) // 2)
        dim = self.t < FADE_SECONDS
        for i, (text, st) in enumerate(lines):
            if text:
                buf.put_center(top + i, truncate(text, buf.width - 2), Style.of("gray") if dim else st)
