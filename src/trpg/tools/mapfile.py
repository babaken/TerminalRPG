"""Map.data の書き換え（マップエディタ用）。

コメントや並び・書式を保ったまま、指定したマップの ``rows = [ ... ]`` だけを置き換える。
TOML 全体を書き直さないので、手で書いた説明や桁揃えはそのまま残る。
"""
from __future__ import annotations

import re
from typing import Optional
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


# ---------------------------------------------------------------- NPC・ワープ・イベント（3-3b）
KINDS = ("npc", "warp", "event")
_ANY_HEADER = re.compile(r"^\s*\[\[?\s*([A-Za-z_][\w.\s-]*?)\s*\]\]?\s*(#.*)?$")


def toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    return quote(str(v))


def read_objects(text: str) -> dict[str, dict[str, list[dict]]]:
    """マップ ID → {"npc": [...], "warp": [...], "event": [...]}（表示用。TOML の辞書のまま）。"""
    data = tomllib.loads(text)
    out = {}
    for m in data.get("map", []):
        if isinstance(m, dict) and isinstance(m.get("id"), str):
            out[m["id"]] = {k: [o for o in m.get(k, []) if isinstance(o, dict)] for k in KINDS}
    return out


def _header_name(line: str) -> Optional[str]:
    m = _ANY_HEADER.match(line)
    return re.sub(r"\s+", "", m.group(1)) if m else None


def _blocks(text: str, map_id: str) -> tuple[list[str], int, int, dict[str, list[tuple[int, int]]]]:
    """行の一覧、マップの範囲（見出しの行〜次のマップ・タイルセットの直前）、種類ごとの表の範囲。"""
    lines = text.splitlines(keepends=True)
    headers = []                                       # (行番号, 見出し名)。rows など複数行の配列の中は除く
    i = 0
    offset = 0
    offsets = []
    for ln in lines:
        offsets.append(offset)
        offset += len(ln)
    while i < len(lines):
        name = _header_name(lines[i])
        if name:
            headers.append((i, name))
        m = _ROWS_KEY.match(lines[i]) or re.match(r"^\s*[\w-]+\s*=\s*(?=\[)", lines[i])
        if m and m.end() < len(lines[i]) and lines[i][m.end()] == "[":
            end = _array_end(text, offsets[i] + m.end())
            while i + 1 < len(lines) and offsets[i + 1] < end:
                i += 1
        i += 1
    for hi, (start, name) in enumerate(headers):
        if not (name == "map" and lines[start].lstrip().startswith("[[")):
            continue
        stop = len(lines)
        for s2, n2 in headers[hi + 1:]:
            if not n2.startswith("map."):
                stop = s2
                break
        mid = None
        body_end = next((s for s, _ in headers if start < s < stop), stop)
        for ln in lines[start + 1: body_end]:
            m = re.match(r"^\s*id\s*=\s*(\"[^\"]*\"|'[^']*')", ln)
            if m:
                mid = m.group(1)[1:-1]
        if mid != map_id:
            continue
        tables: dict[str, list[tuple[int, int]]] = {k: [] for k in KINDS}
        subs = [(s, n) for s, n in headers if start < s < stop]
        for j, (s, n) in enumerate(subs):
            e = subs[j + 1][0] if j + 1 < len(subs) else stop
            while e > s + 1 and (not lines[e - 1].strip() or lines[e - 1].lstrip().startswith("#")):
                e -= 1                                  # 後ろの空行・次の表の説明は含めない
            kind = n.split(".", 1)[1] if "." in n else ""
            if kind in tables:
                tables[kind].append((s, e))
        return lines, start, stop, tables
    raise MapFileError(f"Map.data にマップ {map_id} が見つかりません")


def _check(out: str, map_id: str, kind: str, expect: list[dict]) -> str:
    try:
        got = read_objects(out).get(map_id, {}).get(kind)
    except tomllib.TOMLDecodeError as e:
        raise MapFileError(f"書き換え後の Map.data が TOML として読めません: {e}") from None
    if got != expect:
        raise MapFileError(f"マップ {map_id} の {kind} を正しく書き換えられませんでした")
    return out


def set_object(text: str, map_id: str, kind: str, index: int, values: dict) -> str:
    """index 番目の表の項目を書き換える（None の項目は消す）。ほかの行・コメントはそのまま。"""
    lines, _, _, tables = _blocks(text, map_id)
    before = read_objects(text)[map_id][kind]
    if not 0 <= index < len(tables[kind]) or len(tables[kind]) != len(before):
        raise MapFileError(f"マップ {map_id} の {kind} {index + 1} 番目が見つかりません")
    s, e = tables[kind][index]
    newline = "\r\n" if "\r\n" in text else "\n"
    block = lines[s:e]
    for key, v in values.items():
        pat = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)(\"(?:[^\"\\]|\\.)*\"|'[^']*'|\[[^\]#]*\]|[^#\s]+)(\s*#.*)?(\r?\n)?$")
        at = next((i for i, ln in enumerate(block) if re.match(rf"^\s*{re.escape(key)}\s*=", ln)), None)
        if at is None:
            if v is not None:
                last = max((i for i, ln in enumerate(block) if re.match(r"^\s*[\w-]+\s*=", ln)), default=0)
                block.insert(last + 1, f"{key} = {toml_value(v)}{newline}")
            continue
        if v is None:
            del block[at]
            continue
        m = pat.match(block[at])
        if m:
            block[at] = m.group(1) + toml_value(v) + (m.group(3) or "") + (m.group(4) or "")
        else:
            block[at] = f"{key} = {toml_value(v)}{newline}"
    expect = [dict(o) for o in before]
    for key, v in values.items():
        if v is None:
            expect[index].pop(key, None)
        else:
            expect[index][key] = v
    return _check("".join(lines[:s] + block + lines[e:]), map_id, kind, expect)


def delete_object(text: str, map_id: str, kind: str, index: int) -> str:
    lines, _, _, tables = _blocks(text, map_id)
    before = read_objects(text)[map_id][kind]
    if not 0 <= index < len(tables[kind]) or len(tables[kind]) != len(before):
        raise MapFileError(f"マップ {map_id} の {kind} {index + 1} 番目が見つかりません")
    s, e = tables[kind][index]
    while e < len(lines) and not lines[e].strip():      # 後ろの空行も一緒に消す（空行が続かないように）
        e += 1
    return _check("".join(lines[:s] + lines[e:]), map_id, kind, before[:index] + before[index + 1:])


def add_object(text: str, map_id: str, kind: str, values: dict) -> str:
    """マップの最後に [[map.<kind>]] を足す。None の項目は書かない。"""
    lines, _, stop, _ = _blocks(text, map_id)
    before = read_objects(text)[map_id][kind]
    newline = "\r\n" if "\r\n" in text else "\n"
    e = stop
    while e > 0 and (not lines[e - 1].strip() or (e < len(lines) and lines[e - 1].lstrip().startswith("#"))):
        e -= 1
    if e and not lines[e - 1].endswith("\n"):
        lines[e - 1] += newline
    vals = {k: v for k, v in values.items() if v is not None}
    block = [newline, f"[[map.{kind}]]{newline}"] + [f"{k} = {toml_value(v)}{newline}" for k, v in vals.items()]
    return _check("".join(lines[:e] + block + lines[e:]), map_id, kind, before + [vals])


# ---------------------------------------------------------------- マップの追加（3-3c）
def add_map(text: str, values: dict, rows: list[str]) -> str:
    """ファイルの最後に [[map]] を足す。values は id・name など（None の項目は書かない）、rows は最後に書く。"""
    newline = "\r\n" if "\r\n" in text else "\n"
    if any(m.get("id") == values.get("id") for m in tomllib.loads(text).get("map", [])):
        raise MapFileError(f"マップ {values.get('id')} はすでにあります")
    body = text.rstrip("\r\n") + newline + newline if text.strip() else ""
    body += f"[[map]]{newline}"
    body += "".join(f"{k} = {toml_value(v)}{newline}" for k, v in values.items() if v is not None)
    body += f"rows = {format_rows(rows, '', newline)}{newline}"
    try:
        got = [m for m in tomllib.loads(body).get("map", []) if m.get("id") == values.get("id")]
    except tomllib.TOMLDecodeError as e:
        raise MapFileError(f"書き換え後の Map.data が TOML として読めません: {e}") from None
    if len(got) != 1 or got[0].get("rows") != rows:
        raise MapFileError(f"マップ {values.get('id')} を正しく追加できませんでした")
    return body
