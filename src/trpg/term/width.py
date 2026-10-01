"""文字の表示幅（セル数）計算。

東アジアの文字幅（Unicode East Asian Width）に基づき、全角=2 / 半角=1 / 結合文字=0 を返す。
曖昧幅（A: ─ │ ■ ○ など）は端末やフォントで扱いが異なるため ``set_ambiguous_width`` で切替える。
Windows Terminal の既定は 1。
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache

_ambiguous_width = 1


def set_ambiguous_width(width: int) -> None:
    """曖昧幅文字を何セルとして扱うか（1 または 2）を設定する。"""
    global _ambiguous_width
    if width not in (1, 2):
        raise ValueError("ambiguous width must be 1 or 2")
    _ambiguous_width = width
    char_width.cache_clear()


def get_ambiguous_width() -> int:
    return _ambiguous_width


@lru_cache(maxsize=8192)
def char_width(ch: str) -> int:
    """1 文字の表示セル数（0, 1, 2）。"""
    if not ch:
        return 0
    o = ord(ch[0])
    if o < 0x20 or 0x7F <= o < 0xA0:
        return 0
    if o == 0x200D or 0xFE00 <= o <= 0xFE0F:  # ZWJ / 異体字セレクタ
        return 0
    if unicodedata.combining(ch[0]) or unicodedata.category(ch[0]) in ("Mn", "Me", "Cf"):
        return 0
    eaw = unicodedata.east_asian_width(ch[0])
    if eaw in ("W", "F"):
        return 2
    if eaw == "A":
        return _ambiguous_width
    return 1


def text_width(text: str) -> int:
    """文字列の表示セル数。"""
    return sum(char_width(c) for c in text)


def truncate(text: str, width: int, ellipsis: str = "") -> str:
    """表示幅 ``width`` 以内に収まるよう切り詰める。``ellipsis`` を付ける場合はその幅も含める。"""
    if text_width(text) <= width:
        return text
    limit = width - text_width(ellipsis)
    out = []
    used = 0
    for c in text:
        w = char_width(c)
        if used + w > limit:
            break
        out.append(c)
        used += w
    return "".join(out) + (ellipsis if limit >= 0 else "")


def pad(text: str, width: int, align: str = "left") -> str:
    """表示幅 ``width`` になるよう空白で埋める（はみ出す場合は切り詰め）。"""
    text = truncate(text, width)
    space = width - text_width(text)
    if align == "right":
        return " " * space + text
    if align == "center":
        left = space // 2
        return " " * left + text + " " * (space - left)
    return text + " " * space


def wrap(text: str, width: int) -> list[str]:
    """表示幅で折り返す（日本語向け：単語境界を考慮しない文字単位折り返し）。改行文字でも分割する。"""
    lines: list[str] = []
    for para in text.split("\n"):
        cur = []
        used = 0
        for c in para:
            w = char_width(c)
            if used + w > width and cur:
                lines.append("".join(cur))
                cur, used = [], 0
            cur.append(c)
            used += w
        lines.append("".join(cur))
    return lines
