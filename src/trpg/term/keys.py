"""キーイベントとキー割当（アクション）。"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class Key(Enum):
    CHAR = "CHAR"          # 通常文字（KeyEvent.char に文字）
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    ENTER = "ENTER"
    ESC = "ESC"
    BACKSPACE = "BACKSPACE"
    TAB = "TAB"
    HOME = "HOME"
    END = "END"
    PGUP = "PGUP"
    PGDN = "PGDN"
    INSERT = "INSERT"
    DELETE = "DELETE"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class KeyEvent:
    key: Key
    char: str = ""

    def __str__(self) -> str:
        if self.key is Key.CHAR:
            return repr(self.char)
        return self.key.value


def char_event(ch: str) -> KeyEvent:
    """1 文字を KeyEvent に変換する（Windows / POSIX 共通）。"""
    if ch in ("\r", "\n"):
        return KeyEvent(Key.ENTER)
    if ch == "\x1b":
        return KeyEvent(Key.ESC)
    if ch in ("\x08", "\x7f"):
        return KeyEvent(Key.BACKSPACE)
    if ch == "\t":
        return KeyEvent(Key.TAB)
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch < " ":
        return KeyEvent(Key.UNKNOWN, ch)
    return KeyEvent(Key.CHAR, ch)


class Action(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    OK = "ok"
    CANCEL = "cancel"
    MENU = "menu"
    DEBUG_RELOAD = "debug_reload"


# 要件 6.5: 矢印 / WASD / テンキーで移動、Enter・Z で決定、Esc・X でキャンセル、M でメニュー
DEFAULT_BINDINGS: dict[Action, list[str]] = {
    Action.UP: ["UP", "w", "8"],
    Action.DOWN: ["DOWN", "s", "2"],
    Action.LEFT: ["LEFT", "a", "4"],
    Action.RIGHT: ["RIGHT", "d", "6"],
    Action.OK: ["ENTER", "z", " "],
    Action.CANCEL: ["ESC", "x", "BACKSPACE"],
    Action.MENU: ["m"],
    Action.DEBUG_RELOAD: ["F5"],
}


def _token(ev: KeyEvent) -> str:
    if ev.key is not Key.CHAR:
        return ev.key.value
    # 日本語入力（IME）がオンのまま押すと「ｗ」「８」「　」など全角で届くので半角に揃える
    return unicodedata.normalize("NFKC", ev.char).lower()


class KeyMap:
    """キーイベント → アクション の対応表。

    設定ファイルの例（TOML）::

        [keys]
        up = ["UP", "w", "8", "k"]
        ok = ["ENTER", "z"]
    """

    def __init__(self, bindings: Mapping[Action, Iterable[str]] | None = None):
        self._map: dict[str, set[Action]] = {}
        for action, tokens in (bindings or DEFAULT_BINDINGS).items():
            for t in tokens:
                self.bind(t, action)

    @staticmethod
    def _norm(token: str) -> str:
        return token if token.upper() in Key.__members__ else token.lower()

    def bind(self, token: str, action: Action) -> None:
        self._map.setdefault(self._norm(token), set()).add(action)

    @classmethod
    def from_config(cls, conf: Mapping[str, Iterable[str]]) -> "KeyMap":
        """``{"up": [...]}`` 形式で既定割当を上書きした KeyMap を作る。"""
        bindings = {a: list(t) for a, t in DEFAULT_BINDINGS.items()}
        for name, tokens in conf.items():
            try:
                bindings[Action(name)] = list(tokens)
            except ValueError:
                raise ValueError(f"不明なアクション名です: {name}") from None
        return cls(bindings)

    def actions(self, ev: KeyEvent) -> frozenset[Action]:
        return frozenset(self._map.get(_token(ev), ()))
