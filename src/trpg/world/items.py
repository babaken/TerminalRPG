"""フィールドでのアイテム・スキルの使用（メニューの「どうぐ」「スキル」）。戦闘中の使用は battle.core。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..data.models import GameData, Item, Skill
from .state import GameState, Member


@dataclass
class UseResult:
    used: bool                       # 効果があった（消費した）
    messages: list[str] = field(default_factory=list)
    label: str = ""                  # effect = "script" のとき実行するラベル


def needs_target(it: Item) -> bool:
    return it.use.get("target", "self") in ("ally_one",) and it.use.get("effect") != "script"


def usable_on_field(it: Item) -> bool:
    return bool(it.use) and bool(it.use.get("field"))


def _heal(m: Member, amount: int) -> Optional[str]:
    if not m.alive:
        return f"{m.name}はたおれている。"
    if m.hp >= m.max_hp:
        return f"{m.name}の HP はもう満タンだ。"
    before = m.hp
    m.hp = min(m.max_hp, m.hp + amount)
    return None if m.hp == before else f"{m.name}の HP が {m.hp - before} 回復した！"


def use_item(st: GameState, gd: GameData, iid: str, target: Optional[Member]) -> UseResult:
    it = gd.items[iid]
    if st.items.get(iid, 0) <= 0:
        return UseResult(False, [f"{it.name}を持っていない。"])
    if not usable_on_field(it):
        return UseResult(False, [f"{it.name}はここでは使えない。"])
    use = it.use
    eff = use.get("effect")
    targets = st.party if use.get("target") == "ally_all" else [target or st.hero]
    res = UseResult(False, [f"{st.hero.name if target is None else target.name}に{it.name}を使った。"
                            if target is not None else f"{it.name}を使った。"])
    if eff == "script":
        res.used = True
        res.messages = []
        res.label = use.get("label", "")
    for m in targets:
        if m is None:
            continue
        if eff == "heal":
            msg = _heal(m, int(use.get("power", 0)))
            if msg and "回復した" in msg:
                res.used = True
            res.messages.append(msg or "")
        elif eff == "heal_mp":
            if m.mp >= m.max_mp:
                res.messages.append(f"{m.name}の MP はもう満タンだ。")
            else:
                before = m.mp
                m.mp = min(m.max_mp, m.mp + int(use.get("power", 0)))
                res.used = True
                res.messages.append(f"{m.name}の MP が {m.mp - before} 回復した！")
        elif eff == "cure":
            sid = use.get("status", "")
            if sid in m.status:
                m.status.remove(sid)
                res.used = True
                name = gd.statuses[sid].name if sid in gd.statuses else sid
                res.messages.append(f"{m.name}の{name}が治った！")
            else:
                res.messages.append("しかし、何も起こらなかった。")
        elif eff == "revive":
            if m.hp <= 0:
                m.hp = max(1, m.max_hp * max(1, int(use.get("power", 50))) // 100)
                res.used = True
                res.messages.append(f"{m.name}が生き返った！")
            else:
                res.messages.append("しかし、何も起こらなかった。")
    if res.used and use.get("consume", it.type == "consumable"):
        st.remove_item(iid)
    if not res.used and eff != "script":
        res.messages = [m for m in res.messages[1:] if m] or ["しかし、何も起こらなかった。"]
    res.messages = [m for m in res.messages if m]
    return res


def field_skills(m: Member, gd: GameData) -> list[Skill]:
    """フィールドで使えるスキル（回復系）。"""
    from .growth import skills_of
    return [gd.skills[s] for s in skills_of(m, gd) if gd.skills[s].kind == "heal"]


def use_skill(gd: GameData, user: Member, sk: Skill, target: Optional[Member], party: list[Member]) -> UseResult:
    if user.mp < sk.mp:
        return UseResult(False, ["MP が足りない！"])
    targets = party if sk.target == "ally_all" else [target or user]
    amount = int(sk.power + user.stat("mag", gd) * 0.5)
    msgs = [f"{user.name}は{sk.name}をとなえた！"]
    healed = False
    for m in targets:
        msg = _heal(m, amount)
        healed = healed or bool(msg and "回復した" in msg)
        if msg:
            msgs.append(msg)
    if not healed:
        return UseResult(False, msgs[1:] or ["しかし、何も起こらなかった。"])
    user.mp -= sk.mp
    return UseResult(True, msgs)
