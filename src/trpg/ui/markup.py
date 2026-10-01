"""会話の本文に書ける制御コード（基本設計 10.2）。

    \\w500        ここで 500 ミリ秒待つ
    \\c[red]…\\c[] 文字色を変える（\\c[] で元に戻す）。色名は term.style.COLORS
    \\s2          文字送りの速さを 2 倍に（\\s0.5 で半分、\\s1 で元に戻す、\\s0 で残りを一気に表示）
    \\\\           「\\」そのもの

本文は 1 文字ずつ Glyph（文字・色・直前の待ち時間・速さ）に分解して、会話窓が表示に使う。
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

from ..term.style import COLORS
from ..term.width import char_width

_CODE = re.compile(r"\\(?:w(\d+)|c\[([a-z_]*)\]|s(\d+(?:\.\d+)?)|(\\))")
_ANY_CODE = re.compile(r"\\(w\d*|c\[[^\]]*\]?|s[\d.]*|\\|.)?")


class Glyph(NamedTuple):
    ch: str
    color: Optional[str] = None
    wait: float = 0.0          # この文字を出す前に待つ秒数
    speed: float = 1.0         # 文字送りの速さの倍率（0 なら待たずに出す）


def parse(text: str) -> list[Glyph]:
    """本文を Glyph の列にする。解釈できない制御コードはそのまま文字として残す。"""
    out: list[Glyph] = []
    color: Optional[str] = None
    speed = 1.0
    wait = 0.0
    i = 0
    while i < len(text):
        if text[i] == "\\":
            m = _CODE.match(text, i)
            if m:
                if m.group(1) is not None:
                    wait += int(m.group(1)) / 1000
                elif m.group(2) is not None:
                    color = m.group(2) or None
                elif m.group(3) is not None:
                    speed = float(m.group(3))
                else:
                    out.append(Glyph("\\", color, wait, speed))
                    wait = 0.0
                i = m.end()
                continue
        out.append(Glyph(text[i], color, wait, speed))
        wait = 0.0
        i += 1
    if wait and out:                     # 行末の \w は最後の文字のあとに待つ → 次の文字の前に回せないので空白で表現
        out.append(Glyph("", color, wait, speed))
    return out


def strip(text: str) -> str:
    """制御コードを取り除いた本文（選択肢・検証用）。"""
    return "".join(g.ch for g in parse(text))


def check(text: str) -> list[str]:
    """制御コードの誤り（検証用）。"""
    errors = []
    for m in _ANY_CODE.finditer(text):
        code = m.group(0)
        if _CODE.fullmatch(code):
            name = _CODE.fullmatch(code).group(2)
            if name and name not in COLORS:
                errors.append(f"\\c[{name}] の色名が不正です（{', '.join(sorted(COLORS))}）")
            continue
        errors.append(f"制御コード「{code}」は使えません（\\w ミリ秒 / \\c[色] / \\c[] / \\s 倍率 / \\\\）")
    opened = [m.group(2) for m in _CODE.finditer(text) if m.group(2) is not None]
    if opened and opened[-1] != "":
        errors.append("\\c[色] を \\c[] で閉じていません")
    return errors


def wrap(glyphs: list[Glyph], width: int) -> list[list[Glyph]]:
    """表示幅で折り返す（改行文字でも分割）。"""
    rows: list[list[Glyph]] = []
    cur: list[Glyph] = []
    used = 0
    for g in glyphs:
        if g.ch == "\n":
            rows.append(cur)
            cur, used = [], 0
            continue
        w = char_width(g.ch) if g.ch else 0
        if used + w > width and cur:
            rows.append(cur)
            cur, used = [], 0
        cur.append(g)
        used += w
    rows.append(cur)
    return rows
