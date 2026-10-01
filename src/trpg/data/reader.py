"""TOML テーブルから型チェックしながら値を取り出すヘルパ。

    t = Tbl(data, file="Enemy.data", where="[[enemy]] mole", report=rep, line=12)
    hp = t.int("hp", min=1)
    name = t.str("name")
    t.done()   # 未知のキーを警告（綴り間違いの検出）

不正な値はエラーとして Report に記録し、既定値を返して読み込みを続ける。
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from .report import Report

REQUIRED = object()
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_TYPE_NAMES = {int: "整数", float: "数値", str: "文字列", bool: "true / false", list: "配列", dict: "テーブル"}


class Tbl:
    def __init__(self, data: Any, file: str, where: str, report: Report, line: Optional[int] = None):
        self.file = file
        self.where = where
        self.report = report
        self.line = line
        if not isinstance(data, dict):
            self._err("", "テーブルである必要があります")
            data = {}
        self.data: dict = data
        self.used: set[str] = set()

    # ------------------------------------------------------------------ 内部
    def _label(self, key: str) -> str:
        return f"{self.where} の {key}" if key else self.where

    def _err(self, key: str, msg: str) -> None:
        self.report.error(self.file, self.line, f"{self._label(key)}: {msg}")

    def _warn(self, key: str, msg: str) -> None:
        self.report.warning(self.file, self.line, f"{self._label(key)}: {msg}")

    def has(self, key: str) -> bool:
        return key in self.data

    def _get(self, key: str, default: Any) -> tuple[bool, Any]:
        self.used.add(key)
        if key not in self.data:
            if default is REQUIRED:
                self._err(key, "必須項目がありません")
            return False, None
        return True, self.data[key]

    def _typed(self, key: str, types: tuple, default: Any, fallback: Any) -> Any:
        found, v = self._get(key, default)
        if not found:
            return fallback if default is REQUIRED else default
        if isinstance(v, bool) and bool not in types:
            ok = False
        else:
            ok = isinstance(v, types)
        if not ok:
            self._err(key, f"{_TYPE_NAMES.get(types[0], types[0].__name__)}で指定してください（値: {v!r}）")
            return fallback if default is REQUIRED else default
        return v

    # ------------------------------------------------------------------ 型別
    def str(self, key: str, default: Any = REQUIRED, *, choices: Optional[Iterable[str]] = None) -> str:
        v = self._typed(key, (str,), default, "")
        if choices is not None and v not in choices and key in self.data:
            self._err(key, f"「{v}」は使えません。次のどれかを指定してください: {', '.join(choices)}")
            return default if default is not REQUIRED else next(iter(choices))
        return v

    def id(self, key: str = "id", default: Any = REQUIRED) -> str:
        v = self.str(key, default)
        if v and not ID_RE.match(v):
            self._err(key, f"ID「{v}」は英小文字で始まり、英小文字・数字・_ だけで書いてください")
        return v

    def int(self, key: str, default: Any = REQUIRED, *, min: Optional[int] = None,
            max: Optional[int] = None) -> int:
        v = self._typed(key, (int,), default, 0)
        return self._range(key, v, min, max)

    def num(self, key: str, default: Any = REQUIRED, *, min: Optional[float] = None,
            max: Optional[float] = None) -> float:
        v = self._typed(key, (float, int), default, 0.0)
        return self._range(key, float(v) if v is not None else v, min, max)

    def _range(self, key, v, lo, hi):
        if v is None or key not in self.data:
            return v
        if lo is not None and v < lo:
            self._err(key, f"{lo} 以上にしてください（値: {v}）")
            return lo
        if hi is not None and v > hi:
            self._err(key, f"{hi} 以下にしてください（値: {v}）")
            return hi
        return v

    def bool(self, key: str, default: Any = REQUIRED) -> bool:
        return self._typed(key, (bool,), default, False)

    def strlist(self, key: str, default: Any = REQUIRED) -> list[str]:
        v = self._typed(key, (list,), default, [])
        if v is None:
            return []
        out = []
        for i, item in enumerate(v):
            if not isinstance(item, str):
                self._err(key, f"{i + 1} 番目は文字列で指定してください（値: {item!r}）")
                continue
            out.append(item)
        return out

    def intpair(self, key: str, default: Any = REQUIRED) -> tuple[int, int]:
        v = self._typed(key, (list, int), default, [0, 0])
        if isinstance(v, int) and not isinstance(v, bool):
            return (v, v)
        if v is None:
            return default
        if len(v) != 2 or not all(isinstance(x, int) and not isinstance(x, bool) for x in v):
            self._err(key, f"[最小, 最大] の 2 つの整数で指定してください（値: {v!r}）")
            return (0, 0)
        lo, hi = v
        if lo > hi:
            self._err(key, f"最小が最大より大きくなっています（値: {v!r}）")
            return (hi, lo)
        return (lo, hi)

    def sub(self, key: str, default: Any = REQUIRED) -> "Tbl":
        """入れ子のテーブルを Tbl として返す（無ければ空）。"""
        v = self._typed(key, (dict,), default, {})
        return Tbl(v or {}, self.file, self._label(key), self.report, self.line)

    def table_list(self, key: str, default: Any = REQUIRED) -> list["Tbl"]:
        v = self._typed(key, (list,), default, [])
        out = []
        for i, item in enumerate(v or []):
            out.append(Tbl(item, self.file, f"{self._label(key)} の {i + 1} 番目", self.report, self.line))
        return out

    def raw(self, key: str, default: Any = None) -> Any:
        self.used.add(key)
        return self.data.get(key, default)

    def done(self) -> None:
        """使われなかったキーを警告する（綴り間違い対策）。"""
        for k in self.data:
            if k not in self.used:
                self._warn(k, "未知の項目です（綴りを確認してください）")
