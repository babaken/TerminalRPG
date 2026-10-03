"""フィールドでのアイテム・スキルの使用（メニューの「どうぐ」「スキル」）。戦闘中の使用は battle.core。"""
from __future__ import annotations

from ..i18n import tr

from dataclasses import dataclass, field
from typing import Optional

from ..data.models import GameData, Item, Skill
from .state import GameState, Member


@dataclass
class UseResult:
    used: bool                       # 効果があった（消費した）
    messages: list[str] = field(default_factory=list)
    label: str = ""                  # effect = "script" のとき実行するラベル
    warp: Optional[tuple[str, int, int, str]] = None   # effect = "warp" の行き先（マップ, x, y, 向き）


def needs_target(it: Item) -> bool:
    return it.use.get("target", "self") in ("ally_one",) and it.use.get("effect") not in ("script", "warp")


def _cond(src: str, st: GameState) -> bool:
    from ..script.expr import ExprError, evaluate, parse_expr
    try:
        return bool(evaluate(parse_expr(src), st))
    except ExprError:
        return False


def usable_on_field(it: Item) -> bool:
    return bool(it.use) and bool(it.use.get("field"))


def _heal(m: Member, amount: int) -> Optional[str]:
    if not m.alive:
        return tr('{0}はたおれている。', m.name)
    if m.hp >= m.max_hp:
        return tr('{0}の HP はもう満タンだ。', m.name)
    before = m.hp
    m.hp = min(m.max_hp, m.hp + amount)
    return None if m.hp == before else tr('{0}の HP が {1} 回復した！', m.name, m.hp - before)


def use_item(st: GameState, gd: GameData, iid: str, target: Optional[Member]) -> UseResult:
    it = gd.items[iid]
    if st.items.get(iid, 0) <= 0:
        return UseResult(False, [tr('{0}を持っていない。', it.name)])
    if not usable_on_field(it):
        return UseResult(False, [tr('{0}はここでは使えない。', it.name)])
    use = it.use
    if use.get("when") and not _cond(use["when"], st):
        return UseResult(False, [tr('ここでは使えない。')])
    eff = use.get("effect")
    targets = st.party if use.get("target") == "ally_all" else [target or st.hero]
    res = UseResult(False, [tr('{0}に{1}を使った。', st.hero.name if target is None else target.name, it.name)
                            if target is not None else tr('{0}を使った。', it.name)])
    if eff == "script":
        res.used = True
        res.messages = []
        res.label = use.get("label", "")
    if eff == "warp":
        res.used = True
        res.messages = [tr('{0}を使った！', it.name)]
        res.warp = (use["to"], int(use.get("x", 0)), int(use.get("y", 0)), use.get("dir", ""))
        targets = []
    for m in targets:
        if m is None:
            continue
        if eff == "heal":
            before = m.hp
            msg = _heal(m, int(use.get("power", 0)))
            if m.hp > before:
                res.used = True
            res.messages.append(msg or "")
        elif eff == "heal_mp":
            if m.mp >= m.max_mp:
                res.messages.append(tr('{0}の MP はもう満タンだ。', m.name))
            else:
                before = m.mp
                m.mp = min(m.max_mp, m.mp + int(use.get("power", 0)))
                res.used = True
                res.messages.append(tr('{0}の MP が {1} 回復した！', m.name, m.mp - before))
        elif eff == "cure":
            sid = use.get("status", "")
            if sid in m.status:
                m.status.remove(sid)
                res.used = True
                name = gd.statuses[sid].name if sid in gd.statuses else sid
                res.messages.append(tr('{0}の{1}が治った！', m.name, name))
            else:
                res.messages.append(tr('しかし、何も起こらなかった。'))
        elif eff == "revive":
            if m.hp <= 0:
                m.hp = max(1, m.max_hp * max(1, int(use.get("power", 50))) // 100)
                res.used = True
                res.messages.append(tr('{0}が生き返った！', m.name))
            else:
                res.messages.append(tr('しかし、何も起こらなかった。'))
    if res.used and use.get("consume", it.type == "consumable"):
        st.remove_item(iid)
    if not res.used and eff not in ("script", "warp"):
        res.messages = [m for m in res.messages[1:] if m] or [tr('しかし、何も起こらなかった。')]
    res.messages = [m for m in res.messages if m]
    return res


def field_skills(m: Member, gd: GameData) -> list[Skill]:
    """フィールドで使えるスキル（回復系）。"""
    from .growth import skills_of
    return [gd.skills[s] for s in skills_of(m, gd) if gd.skills[s].kind == "heal"]


def use_skill(gd: GameData, user: Member, sk: Skill, target: Optional[Member], party: list[Member]) -> UseResult:
    if user.mp < sk.mp:
        return UseResult(False, [tr('MP が足りない！')])
    targets = party if sk.target == "ally_all" else [target or user]
    amount = int(sk.power + user.stat("mag", gd) * 0.5)
    msgs = [tr('{0}は{1}をとなえた！', user.name, sk.name)]
    healed = False
    for m in targets:
        before = m.hp
        msg = _heal(m, amount)
        healed = healed or m.hp > before
        if msg:
            msgs.append(msg)
    if not healed:
        return UseResult(False, msgs[1:] or [tr('しかし、何も起こらなかった。')])
    user.mp -= sk.mp
    return UseResult(True, msgs)
