"""見えない罠（Map.data の [[trap]] とマップの traps / trap_kinds）。

- マップに初めて入ったとき、traps = [最小, 最大] の数だけランダムな床に置く（GameState.traps に保存）。
- 踏むまで見えない。踏むと作動して見えるようになる（見えたあとも踏めばまた作動する）。
- 置かない場所：通れないマス・ワープ（階段）・イベント・NPC の初期位置・ほかのマップからワープで着くマス。
- ダメージは最大 HP × damage_rate（最低 1）。罠では HP は 1 より下がらない（罠だけで全滅はしない）。
"""
from __future__ import annotations

from ..i18n import tr

import random
from typing import Optional

from ..data.models import GameData, GameMap, Trap
from .state import GameState


def _blocked(gd: GameData, m: GameMap) -> set[tuple[int, int]]:
    out = {(w.x, w.y) for w in m.warps} | {(e.x, e.y) for e in m.events} | {(n.x, n.y) for n in m.npcs}
    for other in gd.maps.values():                     # ほかのマップから着くマス（階段を降りた直後など）
        out |= {(w.tx, w.ty) for w in other.warps if w.to == m.id}
    return out


def generate(st: GameState, gd: GameData, m: GameMap, rng: Optional[random.Random] = None) -> list[list]:
    """まだ置いていなければ罠を置いて返す。置いたあとは何度呼んでも同じ。"""
    if m.id in st.traps or not m.traps[1]:
        return st.traps.get(m.id, [])
    rng = rng or random
    kinds = [k for k in (m.trap_kinds or list(gd.traps)) if k in gd.traps]
    ts = gd.tilesets.get(m.tileset)
    blocked = _blocked(gd, m)
    cells = [(x, y) for y in range(m.height) for x in range(m.width)
             if ts and (t := ts.tiles.get(m.rows[y][x])) is not None and t.passable and (x, y) not in blocked]
    n = min(len(cells), rng.randint(*m.traps)) if kinds else 0
    st.traps[m.id] = [[x, y, rng.choice(kinds), False] for x, y in rng.sample(cells, n)]
    return st.traps[m.id]


def trap_at(st: GameState, map_id: str, x: int, y: int) -> Optional[list]:
    return next((t for t in st.traps.get(map_id, []) if t[0] == x and t[1] == y), None)


def trigger(st: GameState, gd: GameData, trap: list, rng: Optional[random.Random] = None) -> list[str]:
    """罠を作動させる。見えるようにして、ダメージ・状態異常を与え、表示する文を返す。"""
    rng = rng or random
    kind: Trap = gd.traps[trap[2]]
    trap[3] = True
    alive = [m for m in st.party if m.alive]
    if not alive:
        return []
    targets = alive if kind.target == "all" else [rng.choice(alive)]
    msgs = [kind.message or tr('{0}だ！', kind.name)]
    for m in targets:
        dmg = max(1, int(m.max_hp * kind.damage_rate)) if kind.damage_rate > 0 else 0
        if dmg:
            before = m.hp
            m.hp = max(1, m.hp - dmg)
            msgs.append(tr('{0}は {1} のダメージを受けた！', m.name, before - m.hp))
        if kind.status and kind.status in gd.statuses and kind.status not in m.status:
            m.status.append(kind.status)
            msgs.append(tr('{0}は{1}になった！', m.name, gd.statuses[kind.status].name))
    return msgs
