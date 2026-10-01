"""文字の色・属性と ANSI SGR シーケンス生成。"""
from __future__ import annotations

from typing import NamedTuple, Optional, Union

# 属性ビット
BOLD = 1
DIM = 2
UNDERLINE = 4
REVERSE = 8

COLORS = {
    "black": 0, "red": 1, "green": 2, "yellow": 3,
    "blue": 4, "magenta": 5, "cyan": 6, "white": 7,
    "gray": 8, "grey": 8,
    "bright_red": 9, "bright_green": 10, "bright_yellow": 11,
    "bright_blue": 12, "bright_magenta": 13, "bright_cyan": 14, "bright_white": 15,
}
# AA の .color ファイル用 1 文字コード
COLOR_CODES = {
    "k": 0, "r": 1, "g": 2, "y": 3, "b": 4, "m": 5, "c": 6, "w": 7,
    "K": 8, "R": 9, "G": 10, "Y": 11, "B": 12, "M": 13, "C": 14, "W": 15,
}

ColorSpec = Union[None, int, str]


def color(spec: ColorSpec) -> Optional[int]:
    """色名・番号（0-255）・None（既定色）を色番号に変換する。"""
    if spec is None or spec == "" or spec == "default":
        return None
    if isinstance(spec, int):
        if not 0 <= spec <= 255:
            raise ValueError(f"color out of range: {spec}")
        return spec
    try:
        return COLORS[spec.lower()]
    except KeyError:
        raise ValueError(f"unknown color: {spec}") from None


class Style(NamedTuple):
    fg: Optional[int] = None
    bg: Optional[int] = None
    attrs: int = 0

    @classmethod
    def of(cls, fg: ColorSpec = None, bg: ColorSpec = None, *, bold=False, dim=False,
           underline=False, reverse=False) -> "Style":
        a = (BOLD if bold else 0) | (DIM if dim else 0) | (UNDERLINE if underline else 0) | (REVERSE if reverse else 0)
        return cls(color(fg), color(bg), a)

    def with_fg(self, fg: ColorSpec) -> "Style":
        return self._replace(fg=color(fg))

    def with_bg(self, bg: ColorSpec) -> "Style":
        return self._replace(bg=color(bg))

    def with_attrs(self, attrs: int) -> "Style":
        return self._replace(attrs=self.attrs | attrs)


DEFAULT = Style()

_sgr_cache: dict[Style, str] = {}


def _fg_code(c: int) -> str:
    if c < 8:
        return str(30 + c)
    if c < 16:
        return str(90 + c - 8)
    return f"38;5;{c}"


def _bg_code(c: int) -> str:
    if c < 8:
        return str(40 + c)
    if c < 16:
        return str(100 + c - 8)
    return f"48;5;{c}"


def sgr(style: Style, use_color: bool = True) -> str:
    """スタイルを SGR シーケンスにする。常にリセット(0)から始めるので前状態に依存しない。"""
    key = style if use_color else style._replace(fg=None, bg=None)
    s = _sgr_cache.get(key)
    if s is not None:
        return s
    parts = ["0"]
    if key.attrs & BOLD:
        parts.append("1")
    if key.attrs & DIM:
        parts.append("2")
    if key.attrs & UNDERLINE:
        parts.append("4")
    if key.attrs & REVERSE:
        parts.append("7")
    if key.fg is not None:
        parts.append(_fg_code(key.fg))
    if key.bg is not None:
        parts.append(_bg_code(key.bg))
    s = "\x1b[" + ";".join(parts) + "m"
    _sgr_cache[key] = s
    return s
