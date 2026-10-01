"""クエスト（冒険者協会の依頼）の判定と達成処理（基本設計 9 章）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..data.models import GameData, Quest
from .state import GameState

CondFn = Callable[[str], bool]


def status(st: GameState, qid: str) -> str:
    return st.quests.get(qid, "none")


def available(st: GameState, gd: GameData, cond: CondFn, giver: str = "guild") -> list[Quest]:
    """掲示板に出ている（受注できる）依頼。"""
    out = []
    for q in gd.quests.values():
        if q.giver != giver or not cond(q.when):
            continue
        s = status(st, q.id)
        if s == "none" or (s == "done" and q.repeatable):
            out.append(q)
    return out


def active(st: GameState, gd: GameData) -> list[Quest]:
    return [q for q in gd.quests.values() if status(st, q.id) == "active"]


def accept(st: GameState, q: Quest) -> None:
    st.quests[q.id] = "active"
    st.quest_progress[q.id] = 0


def progress(st: GameState, gd: GameData, q: Quest) -> tuple[int, int]:
    """(現在, 目標)。"""
    g = q.goal
    need = int(g.get("count", 1))
    t = g.get("type")
    if t == "deliver":
        return min(st.items.get(g.get("item", ""), 0), need), need
    if t == "flag":
        return (1 if g.get("flag", "") in st.flags else 0), 1
    if t == "reach":
        return min(st.quest_progress.get(q.id, 0), 1), 1
    return min(st.quest_progress.get(q.id, 0), need), need


def goal_met(st: GameState, gd: GameData, q: Quest) -> bool:
    cur, need = progress(st, gd, q)
    return cur >= need


def goal_text(st: GameState, gd: GameData, q: Quest) -> str:
    g = q.goal
    cur, need = progress(st, gd, q)
    t = g.get("type")
    if t == "deliver":
        it = gd.items.get(g.get("item", ""))
        return f"{it.name if it else g.get('item')} を {need} 個納品（所持 {cur}）"
    if t == "defeat":
        gid = g.get("group", "")
        name = gd.enemies[gid].name if gid in gd.enemies else gid
        if gid in gd.groups:
            names = {gd.enemies[e].name for e in gd.groups[gid].members if e in gd.enemies}
            name = "・".join(sorted(names))
        return f"{name} を {need} 体討伐（{cur}/{need}）"
    if t == "reach":
        mp = gd.maps.get(g.get("map", ""))
        return f"{mp.name if mp else g.get('map')} へ行く（{'済' if cur else '未'}）"
    return "依頼をこなす（" + ("済" if cur else "未") + "）"


def reward_text(gd: GameData, q: Quest) -> str:
    r = q.reward
    parts = []
    if r.get("gold"):
        parts.append(f"{r['gold']} G")
    if r.get("exp"):
        parts.append(f"経験値 {r['exp']}")
    for iid in r.get("items", []):
        it = gd.items.get(iid)
        parts.append(it.name if it else iid)
    return "、".join(parts) or "なし"


@dataclass
class Completion:
    messages: list[str] = field(default_factory=list)
    label: str = ""             # 達成時に実行するスクリプト（on_complete）


def complete(st: GameState, gd: GameData, q: Quest) -> Completion:
    """達成報告。納品物を渡し、報酬を受け取る。"""
    res = Completion()
    g = q.goal
    if g.get("type") == "deliver":
        st.remove_item(g.get("item", ""), int(g.get("count", 1)))
    st.quests[q.id] = "done"
    st.quest_progress.pop(q.id, None)
    r = q.reward
    res.messages.append(f"依頼「{q.name}」を達成した！")
    if r.get("gold"):
        st.gold += r["gold"]
        res.messages.append(f"報酬として {r['gold']} G を受け取った。")
    for iid in r.get("items", []):
        st.add_item(iid)
        it = gd.items.get(iid)
        res.messages.append(f"{it.name if it else iid}を受け取った。")
    if r.get("exp"):
        from .growth import gain_exp
        res.messages += gain_exp(st, gd, r["exp"])
    res.label = q.on_complete
    return res


# ---------------------------------------------------------------- 進行の記録
def on_reach(st: GameState, gd: GameData, map_id: str) -> None:
    for q in active(st, gd):
        if q.goal.get("type") == "reach" and q.goal.get("map") == map_id:
            st.quest_progress[q.id] = 1


def on_defeat(st: GameState, gd: GameData, enemy_ids: list[str], group_id: Optional[str] = None) -> None:
    """戦闘勝利時：倒した敵を討伐依頼に数える。goal.group は敵グループ ID か敵 ID。"""
    for q in active(st, gd):
        if q.goal.get("type") != "defeat":
            continue
        target = q.goal.get("group", "")
        if target in gd.groups:
            if target == group_id:
                st.quest_progress[q.id] = st.quest_progress.get(q.id, 0) + 1
        else:
            n = sum(1 for e in enemy_ids if e == target)
            if n:
                st.quest_progress[q.id] = st.quest_progress.get(q.id, 0) + n
