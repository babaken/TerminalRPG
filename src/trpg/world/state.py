"""ゲームの進行状態（パーティ・所持品・フラグ・位置など）。セーブ対象はすべてここに持つ。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..data.models import STAT_KEYS, GameData
from ..script.expr import ExprError


@dataclass
class Member:
    id: str
    name: str
    job: str
    lv: int
    base: dict[str, int]
    hp: int = 0
    mp: int = 0
    exp: int = 0
    equip: dict[str, str] = field(default_factory=dict)
    status: list[str] = field(default_factory=list)
    extra_skills: list[str] = field(default_factory=list)   # @skill add で覚えたスキル（職業の習得表とは別）
    sp: int = -1              # 技に使う SP（いまの値）。-1 は「最大まで」（古いセーブ・加入直後）

    def max_sp(self, gd: GameData) -> int:
        job = gd.jobs.get(self.job)
        return job.sp_base + job.sp_growth * (self.lv - 1) if job else 0

    def fill_sp(self, gd: GameData) -> None:
        self.sp = self.max_sp(gd)

    def fix_sp(self, gd: GameData) -> None:
        """古いセーブ（SP がない）なら最大に、最大を超えていれば最大にそろえる。"""
        if self.sp < 0 or self.sp > self.max_sp(gd):
            self.fill_sp(gd)

    @property
    def max_hp(self) -> int:
        return self.base.get("hp", 1)

    @property
    def max_mp(self) -> int:
        return self.base.get("mp", 0)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def equip_bonus(self, key: str, gd: GameData) -> int:
        total = 0
        for iid in self.equip.values():
            it = gd.items.get(iid)
            if it is not None:
                total += it.stats.get(key, 0)
        return total

    def stat(self, key: str, gd: GameData) -> int:
        """装備込みの能力値（hp / mp は最大値）。"""
        return self.base.get(key, 0) + self.equip_bonus(key, gd)

    def can_equip(self, iid: str, gd: GameData) -> bool:
        it = gd.items.get(iid)
        job = gd.jobs.get(self.job)
        if it is None or it.type != "equipment" or job is None:
            return False
        return not job.equip or it.category in job.equip

    @classmethod
    def from_data(cls, gd: GameData, cid: str, name: Optional[str] = None) -> "Member":
        c = gd.characters[cid]
        base = {k: c.stats.get(k, 0) for k in STAT_KEYS}
        m = cls(id=c.id, name=name or c.name, job=c.job, lv=c.lv, base=base, equip=dict(c.equip))
        # 途中加入のキャラはそのレベルに見合う累計経験値から始める（growth.exp_for_next と同じ式）
        m.exp = round(10 * (c.lv - 1) ** 2.2) if c.lv > 1 else 0
        m.hp, m.mp = m.max_hp, m.max_mp
        m.fill_sp(gd)
        return m


@dataclass
class GameState:
    party: list[Member] = field(default_factory=list)
    gold: int = 0
    items: dict[str, int] = field(default_factory=dict)
    flags: set[str] = field(default_factory=set)
    vars: dict[str, int] = field(default_factory=dict)
    quests: dict[str, str] = field(default_factory=dict)      # none / active / done / failed
    quest_progress: dict[str, int] = field(default_factory=dict)  # 討伐数など（受注時に 0）
    chapter: int = 0
    chapter_title: str = ""
    map_id: str = ""
    x: int = 0
    y: int = 0
    dir: str = "down"
    once_events: set[str] = field(default_factory=set)
    npc_state: dict[str, dict] = field(default_factory=dict)  # "map:npc" → {hidden, x, y, dir}
    effects: dict[str, str] = field(default_factory=dict)     # 継続エフェクト（tint など）
    playtime: float = 0.0
    last_choice: int = 0
    pet: str = ""            # テイマーが手なずけた魔物（敵 ID）
    tiles: dict[str, dict[str, str]] = field(default_factory=dict)   # @tile で変えたタイル：マップ → {"x,y": 文字}
    away: dict[str, "Member"] = field(default_factory=dict)
    traps: dict[str, list[list]] = field(default_factory=dict)  # 見えない罠：マップ → [[x, y, 種類, 見えたか], ...]  # @party leave keep= で一時的に抜けた仲間（名前 → Member）
    current_map: Any = field(default=None, repr=False, compare=False)  # 今いるマップ（GameMap。セーブしない）

    # ------------------------------------------------------------ 生成
    @classmethod
    def new_game(cls, gd: GameData, manifest, hero_name: Optional[str] = None) -> "GameState":
        st = cls(gold=manifest.start_gold)
        for i, cid in enumerate(manifest.start_party):
            st.party.append(Member.from_data(gd, cid, hero_name if i == 0 else None))
        for iid in manifest.start_items:
            st.add_item(iid)
        return st

    # ------------------------------------------------------------ 操作
    def equip(self, member: "Member", iid: str, gd: GameData) -> Optional[str]:
        """袋のアイテムを装備する（元の装備は袋へ戻す）。外した装備の ID を返す。"""
        it = gd.items[iid]
        old = member.equip.get(it.slot)
        if self.items.get(iid, 0) <= 0:
            return None
        self.remove_item(iid)
        if old:
            self.add_item(old)
        member.equip[it.slot] = iid
        return old

    def unequip(self, member: "Member", slot: str) -> Optional[str]:
        """装備を外して袋に戻す。外した ID を返す。"""
        old = member.equip.pop(slot, None)
        if old:
            self.add_item(old)
        return old

    def add_item(self, iid: str, n: int = 1) -> None:
        self.items[iid] = self.items.get(iid, 0) + n

    def remove_item(self, iid: str, n: int = 1) -> int:
        have = self.items.get(iid, 0)
        take = min(have, n)
        if have - take <= 0:
            self.items.pop(iid, None)
        else:
            self.items[iid] = have - take
        return take

    def member(self, cid: str) -> Optional[Member]:
        return next((m for m in self.party if m.id == cid), None)

    @property
    def hero(self) -> Optional[Member]:
        return self.member("hero") or (self.party[0] if self.party else None)

    def tile_override(self, map_id: str, x: int, y: int) -> Optional[str]:
        return self.tiles.get(map_id, {}).get(f"{x},{y}")

    def set_tile(self, map_id: str, x: int, y: int, ch: str) -> None:
        self.tiles.setdefault(map_id, {})[f"{x},{y}"] = ch

    def npc(self, map_id: str, npc_id: str) -> dict:
        return self.npc_state.setdefault(f"{map_id}:{npc_id}", {})

    # ------------------------------------------------------------ 条件式の評価（script.expr.Context）
    def lookup(self, path: tuple[str, ...]) -> Any:
        root, rest = path[0], path[1:]
        if root == "flag" and len(rest) == 1:
            return rest[0] in self.flags
        if root == "var" and len(rest) == 1:
            return self.vars.get(rest[0], 0)
        if root == "gold" and not rest:
            return self.gold
        if root == "item" and len(rest) == 1:
            return self.items.get(rest[0], 0)
        if root == "quest" and len(rest) == 1:
            return self.quests.get(rest[0], "none")
        if root == "party" and rest == ("size",):
            return len(self.party)
        if root == "choice" and not rest:
            return self.last_choice
        if root == "chapter" and not rest:
            return self.chapter
        if root == "away" and len(rest) == 1:
            m = self.away.get(rest[0])
            return m.id if m else ""
        if root == "pet" and not rest:
            return self.pet
        if root == "map" and not rest:
            return self.map_id
        if root == "map" and rest in (("id",), ("dungeon",), ("dark",), ("indoor",)):
            if rest == ("id",):
                return self.map_id
            return bool(getattr(self.current_map, rest[0], False))
        if root == "self":
            raise ExprError("self.〜 は戦闘中の敵の行動条件でのみ使えます")
        raise ExprError(f"「{'.'.join(path)}」は使えない名前です")

    def call(self, path: tuple[str, ...], args: tuple) -> Any:
        if path == ("party", "has") and len(args) == 1:
            return self.member(str(args[0])) is not None
        if path == ("item", "has") and len(args) == 1:
            return self.items.get(str(args[0]), 0) > 0
        raise ExprError(f"「{'.'.join(path)}(...)」という関数はありません")


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}")


def format_text(text: str, st: GameState, gd: Optional[GameData] = None) -> str:
    """本文中の {hero} {party.2} {var.x} {item.id} {gold} を置き換える。未知のものはそのまま。"""
    def rep(m: re.Match) -> str:
        key = m.group(1)
        parts = key.split(".")
        if key == "hero":
            return st.hero.name if st.hero else ""
        if key == "gold":
            return str(st.gold)
        if parts[0] == "party" and len(parts) == 2 and parts[1].isdigit():
            i = int(parts[1]) - 1
            return st.party[i].name if 0 <= i < len(st.party) else ""
        if parts[0] == "away" and len(parts) == 2:
            m = st.away.get(parts[1])
            return m.name if m else ""
        if parts[0] == "var" and len(parts) == 2:
            return str(st.vars.get(parts[1], 0))
        if parts[0] == "item" and len(parts) == 2 and gd is not None and parts[1] in gd.items:
            return gd.items[parts[1]].name
        return m.group(0)
    return _PLACEHOLDER.sub(rep, text)
