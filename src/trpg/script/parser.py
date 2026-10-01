"""scenario.sco の構文解析（基本設計 10 章）。

テキストを命令列（Instr のリスト）に変換する。@if ブロックはジャンプ命令に展開し、
実行時は命令列を先頭から順に処理するだけで済むようにする。
誤りは行番号つきで Report に集め、可能な限り解析を続ける。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..data.report import Report
from .expr import ExprError, parse_expr, unquote

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
LABEL_RE = re.compile(r"^[A-Za-z0-9_]+$")
SPEAKER_RE = re.compile(r"^(?P<sp>[^\s「」『』@*#]{1,12})「(?P<body>.*)」$")
DIRS = ("up", "down", "left", "right")
RESERVED_LABELS = ("start", "gameover", "on_load")

EFFECTS = ("flash", "fade_in", "fade_out", "shake", "move", "starfall", "rain", "snow",
           "typewriter", "wipe", "blink", "aa_show", "aa_hide", "scroll_text", "tint", "wait")


@dataclass
class Instr:
    op: str                       # msg / choice / jump / jif / goto / call / return / end / cmd
    line: int
    file: str
    args: dict[str, Any] = field(default_factory=dict)

    def where(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass
class Script:
    instrs: list[Instr] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    label_lines: dict[str, tuple[str, int]] = field(default_factory=dict)


# ---------------------------------------------------------------- 引数の分解
_ARG_RE = re.compile(r'\s*(?:(?P<key>[A-Za-z_][A-Za-z0-9_]*)=)?(?P<val>"(?:[^"\\]|\\.)*"|\S+)')


def split_args(text: str) -> tuple[list[str], dict[str, str]]:
    """``a b "c d" key=val key2="x y"`` → (["a","b","c d"], {"key":"val","key2":"x y"})"""
    pos, kw = [], {}
    i = 0
    text = text.rstrip()
    while i < len(text):
        m = _ARG_RE.match(text, i)
        if not m or m.end() == i:
            break
        i = m.end()
        val = m.group("val")
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = unquote(val)
        if m.group("key"):
            kw[m.group("key")] = val
        else:
            pos.append(val)
    return pos, kw


def _is_int(s: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", s))


# 命令ごとの引数仕様。"int" "id" "label" "str" "a|b"（選択肢）、先頭 ? は省略可、"*" は残り全部
SPECS: dict[str, tuple[tuple[str, ...], Optional[set[str]]]] = {
    "goto": (("label",), set()),
    "call": (("label",), set()),
    "return": ((), set()),
    "end": ((), set()),
    "wait": (("int",), set()),
    "keywait": ((), set()),
    "flag": (("set|clear", "name"), set()),
    "item": (("add|remove", "id", "?int"), set()),
    "gold": (("add|remove", "int"), set()),
    "party": (("add|remove", "id"), {"lv"}),
    "equip": (("id", "id"), set()),          # @equip キャラID アイテムID（袋から装備）
    "recruit": (("*",), {"pick", "exclude_party"}),
    "heal": (("all",), set()),
    "quest": (("give|done|fail", "id"), set()),
    "chapter": (("int", "?str"), set()),
    "map": (("id", "int", "int"), {"dir", "transition"}),
    "npc": (("id", "show|hide|move|face", "*"), set()),
    "hero": (("move|face", "*"), set()),
    "face": (("name",), set()),
    "aa": (("show|hide", "*"), {"name"}),
    "effect": (("name", "*"), None),          # キーワードはエフェクトごとに自由
    "shop": (("id",), set()),
    "inn": (("int",), set()),
    "guild": ((), set()),
    "save_point": ((), set()),
    "battle": ((), {"group", "escape", "gameover", "target_only", "lose"}),
    "ending": ((), set()),
}
BLOCK_CMDS = ("if", "elif", "else", "endif", "choice", "var", "include")


class Parser:
    def __init__(self, report: Report, loader: Optional[Callable[[str], Optional[str]]] = None):
        self.rep = report
        self.loader = loader
        self.script = Script()
        self._if_stack: list[dict] = []
        self._msg: Optional[Instr] = None
        self._choice: Optional[Instr] = None
        self._including: list[str] = []

    # ------------------------------------------------------------ 補助
    def err(self, file: str, line: int, msg: str) -> None:
        self.rep.error(file, line, msg)

    def emit(self, ins: Instr) -> int:
        self._msg = None
        self._choice = None
        self.script.instrs.append(ins)
        return len(self.script.instrs) - 1

    @property
    def here(self) -> int:
        return len(self.script.instrs)

    # ------------------------------------------------------------ 入口
    def parse(self, text: str, file: str = "scenario.sco") -> Script:
        self._parse_text(text, file)
        for frame in self._if_stack:
            self.err(frame["file"], frame["line"], "@if に対応する @endif がありません")
        self._if_stack.clear()
        return self.script

    def _logical_lines(self, text: str):
        """行末 \\ の連結を処理しつつ (行番号, 内容) を返す。"""
        buf, start = "", 0
        for no, raw in enumerate(text.splitlines(), 1):
            line = raw.rstrip()
            if not buf:
                start = no
            if line.endswith("\\") and not line.endswith("\\\\"):
                buf += line[:-1]
                continue
            yield start, buf + line
            buf = ""
        if buf:
            yield start, buf

    def _parse_text(self, text: str, file: str) -> None:
        for no, line in self._logical_lines(text):
            s = line.strip()
            if s.startswith("#"):
                continue
            if not s:
                self._msg = None            # 空行 = 改ページ
                continue
            if self._choice is not None and s.startswith("-"):
                self._choice_option(s, file, no)
                continue
            if self._choice is not None and not self._choice.args["options"]:
                self.err(file, no, "@choice の次の行から「- 表示 → *ラベル」の形で選択肢を書いてください")
            self._choice = None
            if s.startswith("*"):
                self._label(s, file, no)
            elif s.startswith("@"):
                self._command(s[1:], file, no)
            else:
                self._text(s, file, no)

    # ------------------------------------------------------------ 各行
    def _label(self, s: str, file: str, no: int) -> None:
        name = s[1:].strip()
        if not LABEL_RE.match(name):
            self.err(file, no, f"ラベル名「{name}」は英数字と _ だけで書いてください")
            return
        if name in self.script.labels:
            f0, l0 = self.script.label_lines[name]
            self.err(file, no, f"ラベル *{name} が重複しています（最初の定義: {f0}:{l0}）")
            return
        self._msg = None
        self.script.labels[name] = self.here
        self.script.label_lines[name] = (file, no)

    def _text(self, s: str, file: str, no: int) -> None:
        m = SPEAKER_RE.match(s)
        speaker = m.group("sp") if m else ""
        if self._msg is None:
            self.emit(Instr("msg", no, file, {"lines": []}))
            self._msg = self.script.instrs[-1]
        self._msg.args["lines"].append((speaker, s))

    def _choice_option(self, s: str, file: str, no: int) -> None:
        body = s[1:].strip()
        label = None
        for arrow in ("→", "->"):
            if arrow in body:
                body, target = body.rsplit(arrow, 1)
                body = body.strip()
                target = target.strip()
                label = target[1:] if target.startswith("*") else target
                if not LABEL_RE.match(label):
                    self.err(file, no, f"選択肢のジャンプ先「{target}」が不正です（*ラベル の形で書いてください）")
                    label = None
                break
        if not body:
            self.err(file, no, "選択肢の表示文がありません")
            return
        self._choice.args["options"].append((body, label, no))

    def _command(self, body: str, file: str, no: int) -> None:
        parts = body.split(None, 1)
        if not parts:
            self.err(file, no, "@ の後に命令名がありません")
            return
        name, rest = parts[0], (parts[1] if len(parts) > 1 else "")
        if name in BLOCK_CMDS:
            getattr(self, f"_cmd_{name}")(rest, file, no)
            return
        spec = SPECS.get(name)
        if spec is None:
            self.err(file, no, f"@{name} という命令はありません")
            return
        pos, kw = split_args(rest)
        if not self._check_args(name, spec, pos, kw, file, no):
            return
        if name in ("goto", "call"):
            label = pos[0][1:] if pos[0].startswith("*") else pos[0]
            self.emit(Instr(name, no, file, {"label": label}))
        elif name in ("return", "end"):
            self.emit(Instr(name, no, file))
        else:
            self.emit(Instr("cmd", no, file, {"name": name, "pos": pos, "kw": kw, "raw": rest}))

    def _check_args(self, name: str, spec, pos: list[str], kw: dict, file: str, no: int) -> bool:
        kinds, allowed_kw = spec
        ok = True
        rest = False
        for i, kind in enumerate(kinds):
            if kind == "*":
                rest = True
                break
            optional = kind.startswith("?")
            kind = kind.lstrip("?")
            if i >= len(pos):
                if not optional:
                    self.err(file, no, f"@{name}: {i + 1} 番目の引数がありません")
                    ok = False
                break
            v = pos[i]
            if kind == "int" and not _is_int(v):
                self.err(file, no, f"@{name}: {i + 1} 番目の引数「{v}」は整数にしてください")
                ok = False
            elif kind == "id" and not ID_RE.match(v):
                self.err(file, no, f"@{name}: ID「{v}」は英小文字・数字・_ で書いてください")
                ok = False
            elif kind == "label":
                lb = v[1:] if v.startswith("*") else v
                if not LABEL_RE.match(lb):
                    self.err(file, no, f"@{name}: ラベル「{v}」が不正です")
                    ok = False
            elif "|" in kind and v not in kind.split("|"):
                self.err(file, no, f"@{name}: 「{v}」は使えません（{kind.replace('|', ' / ')}）")
                ok = False
        if not rest and len(pos) > len(kinds):
            self.err(file, no, f"@{name}: 引数が多すぎます（「{' '.join(pos[len(kinds):])}」）")
            ok = False
        if allowed_kw is not None:
            for k in kw:
                if k not in allowed_kw:
                    hint = f"（使えるのは {', '.join(sorted(allowed_kw))}）" if allowed_kw else ""
                    self.err(file, no, f"@{name}: {k}= は指定できません{hint}")
                    ok = False
        ok = self._check_specific(name, pos, kw, file, no) and ok
        return ok

    def _check_specific(self, name: str, pos: list[str], kw: dict, file: str, no: int) -> bool:
        def bad(msg: str) -> bool:
            self.err(file, no, f"@{name}: {msg}")
            return False

        if name == "npc" and len(pos) >= 2:
            act, extra = pos[1], pos[2:]
            if act == "move" and (len(extra) != 2 or not all(_is_int(x) for x in extra)):
                return bad("move の後に移動量 dx dy（整数 2 つ）を書いてください")
            if act == "face" and (len(extra) != 1 or extra[0] not in DIRS):
                return bad(f"face の後に向き（{' / '.join(DIRS)}）を書いてください")
            if act in ("show", "hide") and extra:
                return bad(f"{act} に余分な引数があります")
        if name == "hero" and pos:
            act, extra = pos[0], pos[1:]
            if act == "move" and (len(extra) != 2 or not all(_is_int(x) for x in extra)):
                return bad("move の後に移動量 dx dy（整数 2 つ）を書いてください")
            if act == "face" and (len(extra) != 1 or extra[0] not in DIRS):
                return bad(f"face の後に向き（{' / '.join(DIRS)}）を書いてください")
        if name == "map":
            if "dir" in kw and kw["dir"] not in DIRS:
                return bad(f"dir は {' / '.join(DIRS)} のどれかです")
            if "transition" in kw and kw["transition"] not in ("none", "fade", "wipe"):
                return bad("transition は none / fade / wipe のどれかです")
        if name == "battle":
            if "group" not in kw:
                return bad("group=敵グループID を指定してください")
            if "gameover" in kw and kw["gameover"] not in ("retry_from_save", "title", "choose"):
                return bad("gameover は retry_from_save / title / choose のどれかです")
            if "escape" in kw and kw["escape"] not in ("true", "false"):
                return bad("escape は true / false です")
        if name == "party" and "lv" in kw and not (kw["lv"] == "avg" or _is_int(kw["lv"])):
            return bad("lv は整数か avg です")
        if name == "recruit":
            if not pos:
                return bad("候補のキャラクター ID を 1 つ以上書いてください")
            if "pick" in kw and not _is_int(kw["pick"]):
                return bad("pick は整数です")
        if name == "effect" and pos and pos[0] not in EFFECTS:
            return bad(f"エフェクト「{pos[0]}」はありません（{', '.join(EFFECTS)}）")
        if name == "aa" and pos:
            if pos[0] == "show" and (len(pos) < 4 or not _is_int(pos[2]) or not _is_int(pos[3])):
                return bad("show の後に ファイル x y を書いてください")
            if pos[0] == "hide" and len(pos) != 2:
                return bad("hide の後に AA の名前を書いてください")
        return True

    # ------------------------------------------------------------ ブロック命令
    def _cond(self, rest: str, file: str, no: int):
        try:
            return parse_expr(rest)
        except ExprError as e:
            self.err(file, no, f"条件式の誤り: {e}")
            return ("lit", False)

    def _cmd_if(self, rest: str, file: str, no: int) -> None:
        ast = self._cond(rest, file, no)
        idx = self.emit(Instr("jif", no, file, {"cond": ast, "src": rest.strip(), "target": None}))
        self._if_stack.append({"jif": idx, "ends": [], "else": False, "file": file, "line": no})

    def _cmd_elif(self, rest: str, file: str, no: int) -> None:
        if not self._if_stack:
            self.err(file, no, "@elif の前に @if がありません")
            return
        fr = self._if_stack[-1]
        if fr["else"]:
            self.err(file, no, "@else の後に @elif は書けません")
            return
        fr["ends"].append(self.emit(Instr("jump", no, file, {"target": None})))
        self.script.instrs[fr["jif"]].args["target"] = self.here
        ast = self._cond(rest, file, no)
        fr["jif"] = self.emit(Instr("jif", no, file, {"cond": ast, "src": rest.strip(), "target": None}))

    def _cmd_else(self, rest: str, file: str, no: int) -> None:
        if not self._if_stack:
            self.err(file, no, "@else の前に @if がありません")
            return
        fr = self._if_stack[-1]
        if fr["else"]:
            self.err(file, no, "@else が 2 回あります")
            return
        fr["ends"].append(self.emit(Instr("jump", no, file, {"target": None})))
        self.script.instrs[fr["jif"]].args["target"] = self.here
        fr["jif"] = None
        fr["else"] = True

    def _cmd_endif(self, rest: str, file: str, no: int) -> None:
        if not self._if_stack:
            self.err(file, no, "@endif に対応する @if がありません")
            return
        fr = self._if_stack.pop()
        if fr["jif"] is not None:
            self.script.instrs[fr["jif"]].args["target"] = self.here
        for j in fr["ends"]:
            self.script.instrs[j].args["target"] = self.here
        self._msg = None

    def _cmd_choice(self, rest: str, file: str, no: int) -> None:
        if rest.strip():
            self.err(file, no, "@choice の選択肢は次の行から「- 表示 → *ラベル」の形で書いてください")
        self.emit(Instr("choice", no, file, {"options": []}))
        self._choice = self.script.instrs[-1]

    _VAR_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>=|\+=|-=)\s*(?P<expr>.+)$")

    def _cmd_var(self, rest: str, file: str, no: int) -> None:
        m = self._VAR_RE.match(rest.strip())
        if not m:
            self.err(file, no, "@var は「@var 名前 = 式」（+= / -= も可）の形で書いてください")
            return
        name = m.group("name")
        if name.startswith("var."):
            name = name[4:]
        ast = self._cond(m.group("expr"), file, no)
        self.emit(Instr("cmd", no, file, {"name": "var", "var": name, "op": m.group("op"), "expr": ast,
                                         "pos": [], "kw": {}, "raw": rest}))

    def _cmd_include(self, rest: str, file: str, no: int) -> None:
        pos, _ = split_args(rest)
        if len(pos) != 1:
            self.err(file, no, '@include "ファイル名" の形で書いてください')
            return
        target = pos[0]
        if self.loader is None:
            self.err(file, no, "@include はここでは使えません")
            return
        if target in self._including or target == file:
            self.err(file, no, f"@include が循環しています: {target}")
            return
        text = self.loader(target)
        if text is None:
            self.err(file, no, f"@include のファイル「{target}」が見つかりません")
            return
        self._msg = None
        self._choice = None
        self._including.append(file)
        try:
            self._parse_text(text, target)
        finally:
            self._including.pop()
        self._msg = None


def parse_script(text: str, report: Report, file: str = "scenario.sco",
                 loader: Optional[Callable[[str], Optional[str]]] = None) -> Script:
    """スクリプトを解析する。誤りは report に入る（解析結果は誤り部分を除いて返す）。"""
    return Parser(report, loader).parse(text, file)
