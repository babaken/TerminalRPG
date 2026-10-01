"""Map.data の書き換え（マップエディタ用）。

コメントや並び・書式を保ったまま、指定したマップの ``rows = [ ... ]`` だけを置き換える。
TOML 全体を書き直さないので、手で書いた説明や桁揃えはそのまま残る。
"""
from __future__ import annotations

import re
import tomllib

_HEADER = re.compile(r"^\s*\[")                     # テーブル見出し（[x] / [[x]]）
_MAP_HEADER = re.compile(r"^\s*\[\[\s*map\s*\]\]\s*(#.*)?$")
_ROWS_KEY = re.compile(r"^(\s*)rows\s*=\s*")


class MapFileError(Exception):
    """書き換えられない。メッセージは利用者向けの日本語。"""


def quote(s: str) -> str:
    """TOML の基本文字列にする（" と \\ だけエスケープ。タイルの文字に使われることがある）。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _array_end(text: str, start: int) -> int:
    """text[start] の '[' に対応する ']' の次の位置。文字列とコメントの中の括弧は数えない。"""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in "\"'":
            if text.startswith(c * 3, i):            # 複数行文字列
                end = text.find(c * 3, i + 3)
                if end < 0:
                    break
                i = end + 3
                continue
            i += 1
            while i < n and text[i] != c and text[i] != "\n":
                if c == '"' and text[i] == "\\":
                    i += 1
                i += 1
            i += 1
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise MapFileError("rows の配列の終わり（]）が見つかりません")


def _find_rows(text: str, map_id: str) -> tuple[int, int, str]:
    """マップ map_id の rows 配列の位置（'[' の位置、']' の次の位置、行頭の字下げ）。"""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))
    i = 0
    while i < len(lines):
        if not _MAP_HEADER.match(lines[i]):
            i += 1
            continue
        j = i + 1
        found_id = None
        rows_at = None
        while j < len(lines) and not _HEADER.match(lines[j]):
            m = re.match(r"^\s*id\s*=\s*(\"[^\"]*\"|'[^']*')", lines[j])
            if m:
                found_id = m.group(1)[1:-1]
            m = _ROWS_KEY.match(lines[j])
            if m and rows_at is None:
                rows_at = (j, m)
                # 複数行の配列の中にある見出しのような行を読み飛ばす
                end = _array_end(text, offsets[j] + m.end())
                while j + 1 < len(lines) and offsets[j + 1] < end:
                    j += 1
            j += 1
        if found_id == map_id:
            if rows_at is None:
                raise MapFileError(f"マップ {map_id} に rows がありません")
            k, m = rows_at
            start = offsets[k] + m.end()
            if start >= len(text) or text[start] != "[":
                raise MapFileError(f"マップ {map_id} の rows が配列ではありません")
            return start, _array_end(text, start), m.group(1)
        i = j
    raise MapFileError(f"Map.data にマップ {map_id} が見つかりません")


def format_rows(rows: list[str], indent: str = "", newline: str = "\n") -> str:
    body = "".join(f"{indent}  {quote(r)},{newline}" for r in rows)
    return f"[{newline}{body}{indent}]"


def replace_rows(text: str, map_id: str, rows: list[str]) -> str:
    """Map.data の本文の、マップ map_id の rows を置き換えた本文を返す。"""
    newline = "\r\n" if "\r\n" in text else "\n"
    start, end, indent = _find_rows(text, map_id)
    out = text[:start] + format_rows(rows, indent, newline) + text[end:]
    # 置き換えた結果が TOML として正しく、狙ったマップだけが変わったことを確かめる
    try:
        data = tomllib.loads(out)
    except tomllib.TOMLDecodeError as e:
        raise MapFileError(f"書き換え後の Map.data が TOML として読めません: {e}") from None
    got = [m.get("rows") for m in data.get("map", []) if m.get("id") == map_id]
    if got != [rows]:
        raise MapFileError(f"マップ {map_id} の rows を正しく書き換えられませんでした")
    return out
