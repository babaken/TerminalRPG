"""条件式（@if / when / @var の右辺）の構文解析と評価。

    flag.found_sword and not flag.ch1_done
    gold >= 100 and var.ch1_quests >= 3
    party.has(garo) or party.size == 4
    quest.q_mole == done
    !flag.lost_friend

名前空間（基本設計 10.4）:
    flag.X  真偽（未定義は false）     var.X   整数（未定義は 0）
    gold    所持金                      item.X  所持数
    party.size / party.has(ID)          quest.X 状態（none / active / done / failed）
    choice  直前の選択肢の番号（1 始まり）  chapter 現在の章番号
    map     今いるマップの ID（map == dungeon_b03）  map.dungeon / map.dark / map.indoor  マップの設定
    self.hp_rate など（戦闘中の敵 AI 用。フィールドでは使えない）
ドットを含まない未知の名前（done など）は文字列として扱う。
"""
from __future__ import annotations

import re
from typing import Any, Iterator, Protocol

ROOTS = ("flag", "var", "gold", "item", "party", "quest", "choice", "chapter", "map", "self")


class ExprError(Exception):
    pass


_TOKEN = re.compile(r"""
    \s*(?:
      (?P<num>\d+(?:\.\d+)?)
    | (?P<str>"(?:[^"\\]|\\.)*")
    | (?P<op>==|!=|<=|>=|<|>|\(|\)|,|!|-)
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
    )""", re.X)


def unquote(s: str) -> str:
    """ "..." の引用符を外し、\\" と \\\\ だけを元に戻す（日本語をそのまま保つ）。"""
    return re.sub(r'\\(["\\])', r"\1", s[1:-1])


def tokenize(src: str) -> list[tuple[str, str]]:
    out = []
    pos = 0
    src = src.rstrip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise ExprError(f"式を解釈できません: 「{src[pos:].strip()}」")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "name" and val in ("and", "or", "not", "true", "false"):
            kind = "kw"
        out.append((kind, val))
    return out


class _Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = tokenize(src)
        self.i = 0

    def peek(self, kind: str | None = None, val: str | None = None) -> bool:
        if self.i >= len(self.toks):
            return False
        k, v = self.toks[self.i]
        return (kind is None or k == kind) and (val is None or v == val)

    def take(self) -> tuple[str, str]:
        if self.i >= len(self.toks):
            raise ExprError(f"式が途中で終わっています: 「{self.src}」")
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind: str, val: str) -> None:
        k, v = self.take()
        if (k, v) != (kind, val):
            raise ExprError(f"「{val}」が必要です（「{v}」があります）: 「{self.src}」")

    def parse(self):
        if not self.toks:
            raise ExprError("条件式が空です")
        node = self.or_()
        if self.i != len(self.toks):
            raise ExprError(f"余分な「{self.toks[self.i][1]}」があります: 「{self.src}」")
        return node

    def or_(self):
        node = self.and_()
        while self.peek("kw", "or"):
            self.take()
            node = ("or", node, self.and_())
        return node

    def and_(self):
        node = self.not_()
        while self.peek("kw", "and"):
            self.take()
            node = ("and", node, self.not_())
        return node

    def not_(self):
        if self.peek("kw", "not") or self.peek("op", "!"):
            self.take()
            return ("not", self.not_())
        return self.cmp()

    def cmp(self):
        node = self.atom()
        if self.peek("op") and self.toks[self.i][1] in ("==", "!=", "<", "<=", ">", ">="):
            op = self.take()[1]
            node = ("cmp", op, node, self.atom())
        return node

    def atom(self):
        k, v = self.take()
        if k == "num":
            return ("lit", float(v) if "." in v else int(v))
        if k == "str":
            return ("lit", unquote(v))
        if k == "kw" and v in ("true", "false"):
            return ("lit", v == "true")
        if k == "op" and v == "(":
            node = self.or_()
            self.expect("op", ")")
            return node
        if k == "op" and v == "-":
            k2, v2 = self.take()
            if k2 != "num":
                raise ExprError(f"「-」の後には数値が必要です: 「{self.src}」")
            return ("lit", -(float(v2) if "." in v2 else int(v2)))
        if k == "name":
            path = tuple(v.split("."))
            if self.peek("op", "("):
                self.take()
                args = []
                if not self.peek("op", ")"):
                    args.append(self._arg())
                    while self.peek("op", ","):
                        self.take()
                        args.append(self._arg())
                self.expect("op", ")")
                return ("call", path, tuple(args))
            if len(path) == 1 and path[0] not in ROOTS:
                return ("lit", path[0])        # done / active などの裸の単語
            if path[0] not in ROOTS:
                raise ExprError(f"「{v}」は使えない名前です（使える名前: {', '.join(ROOTS)}）")
            return ("name", path)
        raise ExprError(f"「{v}」は式の中で使えません: 「{self.src}」")

    def _arg(self):
        k, v = self.take()
        if k in ("name",):
            return v
        if k == "num":
            return int(v)
        if k == "str":
            return unquote(v)
        raise ExprError(f"関数の引数「{v}」が不正です")


def parse_expr(src: str):
    """式を構文解析して AST を返す。誤りは ExprError。"""
    return _Parser(src).parse()


class Context(Protocol):
    def lookup(self, path: tuple[str, ...]) -> Any: ...
    def call(self, path: tuple[str, ...], args: tuple) -> Any: ...


def evaluate(node, ctx: Context) -> Any:
    op = node[0]
    if op == "lit":
        return node[1]
    if op == "name":
        return ctx.lookup(node[1])
    if op == "call":
        return ctx.call(node[1], node[2])
    if op == "not":
        return not evaluate(node[1], ctx)
    if op == "and":
        return bool(evaluate(node[1], ctx)) and bool(evaluate(node[2], ctx))
    if op == "or":
        return bool(evaluate(node[1], ctx)) or bool(evaluate(node[2], ctx))
    if op == "cmp":
        a, b = evaluate(node[2], ctx), evaluate(node[3], ctx)
        o = node[1]
        if o == "==":
            return a == b
        if o == "!=":
            return a != b
        try:
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[o]
        except TypeError:
            raise ExprError(f"{a!r} と {b!r} は大小比較できません") from None
    raise ExprError(f"unknown node {op}")


def names(node) -> Iterator[tuple[str, ...]]:
    """式が参照している名前（検証用）。関数呼び出しは (path..., 引数) で返す。"""
    op = node[0]
    if op == "name":
        yield node[1]
    elif op == "call":
        yield node[1] + tuple(str(a) for a in node[2])
    elif op in ("not",):
        yield from names(node[1])
    elif op in ("and", "or"):
        yield from names(node[1])
        yield from names(node[2])
    elif op == "cmp":
        yield from names(node[2])
        yield from names(node[3])
