"""スクリプト実行機（VM）。

命令を順に実行し、プレイヤーの操作や時間経過を待つ必要がある所で「要求」を返して止まる。
呼び出し側（フィールド画面など）は要求を処理し終えたら ``step()`` を呼んで再開する。

    vm.start("start")
    req = vm.step()          # MessageReq / ChoiceReq / WaitReq / ... / None（終了）
    ...表示してキー待ち...
    req = vm.step()

状態を変えるだけの命令（@flag @var @item @gold @party @heal @quest @chapter）は VM 内で処理する。
画面や世界に関わる命令（@map @npc @effect @battle ...）は host.exec_cmd() に任せる。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from ..data.models import GameData
from ..world.state import GameState, Member, format_text
from .expr import ExprError, evaluate
from .parser import Instr, Script

MAX_STEPS = 100_000   # 待ちなしで実行できる命令数の上限（無限ループ検出）


class ScriptError(Exception):
    def __init__(self, ins: Optional[Instr], msg: str):
        self.ins = ins
        where = f"{ins.where()} " if ins else ""
        super().__init__(f"{where}{msg}")


# ---------------------------------------------------------------- 要求
@dataclass
class MessageReq:
    lines: list[tuple[str, str]]      # (話者, 表示文)


@dataclass
class ChoiceReq:
    options: list[str]


@dataclass
class WaitReq:
    seconds: float


@dataclass
class KeyWaitReq:
    pass


class Host(Protocol):
    def exec_cmd(self, ins: Instr) -> Optional[object]:
        """命令を実行する。処理完了を待つ必要があれば要求オブジェクトを返す。"""


class VM:
    def __init__(self, script: Script, state: GameState, gd: GameData, host: Host):
        self.script = script
        self.state = state
        self.gd = gd
        self.host = host
        self.pc: Optional[int] = None
        self.stack: list[int] = []
        self._pending_choice: Optional[Instr] = None

    @property
    def running(self) -> bool:
        return self.pc is not None

    def has_label(self, label: str) -> bool:
        return label in self.script.labels

    def start(self, label: str) -> None:
        if label not in self.script.labels:
            raise ScriptError(None, f"ラベル *{label} がありません")
        self.pc = self.script.labels[label]
        self.stack.clear()
        self._pending_choice = None

    def stop(self) -> None:
        self.pc = None
        self.stack.clear()
        self._pending_choice = None

    def choose(self, index: int) -> None:
        """選択肢の結果（0 始まり）を渡す。"""
        ins = self._pending_choice
        if ins is None:
            return
        self._pending_choice = None
        self.state.last_choice = index + 1
        _, label, _ = ins.args["options"][index]
        if label:
            self._jump_label(ins, label)

    def jump(self, label: str) -> None:
        """実行中のスクリプトを label へ飛ばす（呼び出し履歴は保つ）。負けイベントの lose= などで使う。"""
        self._jump_label(None, label.lstrip("*"))

    def _jump_label(self, ins: Instr, label: str) -> None:
        if label not in self.script.labels:
            raise ScriptError(ins, f"ラベル *{label} がありません")
        self.pc = self.script.labels[label]

    def _eval(self, ins: Instr, ast):
        try:
            return evaluate(ast, self.state)
        except ExprError as e:
            raise ScriptError(ins, str(e)) from None

    # ------------------------------------------------------------ 実行
    def step(self) -> Optional[object]:
        """次の要求まで実行する。終了したら None。"""
        if self._pending_choice is not None:
            raise ScriptError(self._pending_choice, "選択肢の結果が渡されていません")
        n = 0
        instrs = self.script.instrs
        while self.pc is not None:
            if self.pc >= len(instrs):
                self.stop()
                break
            n += 1
            if n > MAX_STEPS:
                raise ScriptError(instrs[self.pc], "命令が止まらずに実行され続けています（@goto の無限ループの可能性）")
            ins = instrs[self.pc]
            self.pc += 1
            op = ins.op
            if op == "msg":
                return MessageReq([(sp, format_text(t, self.state, self.gd)) for sp, t in ins.args["lines"]])
            if op == "choice":
                self._pending_choice = ins
                return ChoiceReq([format_text(t, self.state, self.gd) for t, _, _ in ins.args["options"]])
            if op == "jump":
                self.pc = ins.args["target"]
            elif op == "jif":
                if not self._eval(ins, ins.args["cond"]):
                    self.pc = ins.args["target"]
            elif op == "goto":
                self._jump_label(ins, ins.args["label"])
            elif op == "call":
                self.stack.append(self.pc)
                self._jump_label(ins, ins.args["label"])
            elif op == "return":
                if self.stack:
                    self.pc = self.stack.pop()
                else:
                    self.stop()
            elif op == "end":
                self.stop()
            elif op == "cmd":
                req = self._cmd(ins)
                if req is not None:
                    return req
        return None

    def _cmd(self, ins: Instr) -> Optional[object]:
        a = ins.args
        name, pos, kw = a["name"], a["pos"], a["kw"]
        st = self.state
        if name == "flag":
            (st.flags.add if pos[0] == "set" else st.flags.discard)(pos[1])
        elif name == "var":
            v = self._eval(ins, a["expr"])
            if isinstance(v, bool):
                v = int(v)
            if not isinstance(v, (int, float)):
                raise ScriptError(ins, f"@var の値が数値ではありません（{v!r}）")
            cur = st.vars.get(a["var"], 0)
            st.vars[a["var"]] = int({"=": v, "+=": cur + v, "-=": cur - v}[a["op"]])
        elif name == "item":
            n = int(pos[2]) if len(pos) > 2 else 1
            if pos[1] not in self.gd.items:
                raise ScriptError(ins, f"アイテム「{pos[1]}」が定義されていません")
            if pos[0] == "add":
                st.add_item(pos[1], n)
            else:
                st.remove_item(pos[1], n)
        elif name == "gold":
            n = int(pos[1])
            st.gold = st.gold + n if pos[0] == "add" else max(0, st.gold - n)
        elif name == "party":
            cid = pos[1]
            if pos[0] == "add":
                if cid not in self.gd.characters:
                    raise ScriptError(ins, f"キャラクター「{cid}」が定義されていません")
                if st.member(cid) is None:
                    from ..world.growth import raise_to_level, resolve_level
                    target = resolve_level(st, kw.get("lv", ""))     # 加入する本人を含めず、いまのパーティで計算
                    m = Member.from_data(self.gd, cid)
                    raise_to_level(m, self.gd, target)
                    st.party.append(m)
            else:
                st.party = [m for m in st.party if m.id != cid]
        elif name == "equip":
            m = st.member(pos[0])
            it = self.gd.items.get(pos[1])
            if m is None:
                raise ScriptError(ins, f"「{pos[0]}」はパーティにいません")
            if it is None or it.type != "equipment":
                raise ScriptError(ins, f"「{pos[1]}」は装備品ではありません")
            if st.items.get(pos[1], 0) <= 0:
                raise ScriptError(ins, f"「{it.name}」を持っていません（先に @item add してください）")
            st.equip(m, pos[1], self.gd)
        elif name == "heal":
            for m in st.party:
                m.hp, m.mp = m.max_hp, m.max_mp
                m.status.clear()
        elif name == "quest":
            st.quests[pos[1]] = {"give": "active", "done": "done", "fail": "failed"}[pos[0]]
            if pos[0] == "give":
                st.quest_progress[pos[1]] = 0
        elif name == "chapter":
            st.chapter = int(pos[0])
            st.chapter_title = pos[1] if len(pos) > 1 else ""
        elif name == "tile":
            mid = kw.get("map") or st.map_id
            mp = self.gd.maps.get(mid)
            x, y, ch = int(pos[0]), int(pos[1]), pos[2]
            if mp is None:
                raise ScriptError(ins, f"@tile：マップ「{mid}」が定義されていません")
            if not mp.in_bounds(x, y):
                raise ScriptError(ins, f"@tile：座標 ({x}, {y}) がマップ {mid} の外です")
            ts = self.gd.tilesets.get(mp.tileset)
            if len(ch) != 1 or ts is None or ch not in ts.tiles:
                raise ScriptError(ins, f"@tile：「{ch}」はマップ {mid} のタイルセットにありません")
            st.set_tile(mid, x, y, ch)
        elif name == "wait":
            return WaitReq(int(pos[0]) / 1000)
        elif name == "keywait":
            return KeyWaitReq()
        else:
            return self.host.exec_cmd(ins)
        return None
