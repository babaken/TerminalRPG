"""経験値とレベルアップ（基本設計 14 章）。"""
from __future__ import annotations

import random
from typing import Optional

from ..data.models import STAT_KEYS, GameData
from .state import GameState, Member

MAX_LV = 99


def exp_for_next(lv: int) -> int:
    """Lv ``lv`` から次のレベルに上がるのに必要な累計経験値。"""
    return round(10 * lv ** 2.2)


def skills_of(m: Member, gd: GameData) -> list[str]:
    """現在のレベルで使えるスキル ID（職業の習得表から）。"""
    job = gd.jobs.get(m.job)
    out = [sid for lv, sid in job.skills if lv <= m.lv and sid in gd.skills] if job else []
    out += [sid for sid in m.extra_skills if sid in gd.skills and sid not in out]
    return out


def level_up(m: Member, gd: GameData, rng: Optional[random.Random] = None) -> list[str]:
    """1 レベル上げる。上昇内容と新しく覚えたスキルのメッセージを返す。"""
    rng = rng or random
    job = gd.jobs.get(m.job)
    before = set(skills_of(m, gd))
    m.lv += 1
    gains = []
    for k in STAT_KEYS:
        g = job.growth.get(k, 0) if job else 0
        if g <= 0:
            continue
        inc = max(0, g + rng.choice((-1, 0, 0, 1)))
        if inc:
            m.base[k] = m.base.get(k, 0) + inc
            if k == "hp":
                m.hp += inc
            elif k == "mp":
                m.mp += inc
            gains.append((k, inc))
    msgs = [f"{m.name}はレベル {m.lv} に上がった！"]
    for sid in skills_of(m, gd):
        if sid not in before:
            msgs.append(f"{m.name}は{gd.skills[sid].name}を覚えた！")
    return msgs


def party_avg_level(st: GameState) -> int:
    """パーティの平均レベル（四捨五入、最低 1）。"""
    if not st.party:
        return 1
    return max(1, round(sum(m.lv for m in st.party) / len(st.party)))


def resolve_level(st: GameState, spec: str) -> Optional[int]:
    """lv= の指定（"avg" か数値）を目標レベルにする。空なら None。"""
    if not spec:
        return None
    if spec == "avg":
        return party_avg_level(st)
    return max(1, min(MAX_LV, int(spec)))


def raise_to_level(m: Member, gd: GameData, target: Optional[int], rng: Optional[random.Random] = None) -> None:
    """加入時に target までレベルを上げる（職業の成長どおり）。もともと高ければそのまま。HP・MP は満タン。"""
    if target is not None:
        while m.lv < min(target, MAX_LV):
            level_up(m, gd, rng)
        m.exp = max(m.exp, exp_for_next(m.lv - 1) if m.lv > 1 else 0)
    m.hp, m.mp = m.stat("hp", gd), m.stat("mp", gd)


def gain_exp(st: GameState, gd: GameData, total: int, rng: Optional[random.Random] = None) -> list[str]:
    """生存メンバーで経験値を均等に分ける。レベルアップのメッセージを返す。"""
    alive = [m for m in st.party if m.alive]
    if not alive or total <= 0:
        return []
    share = max(1, total // len(alive))
    msgs = [f"それぞれ {share} の経験値を得た。" if len(alive) > 1 else f"{alive[0].name}は {share} の経験値を得た。"]
    for m in alive:
        m.exp += share
        while m.lv < MAX_LV and m.exp >= exp_for_next(m.lv):
            msgs += level_up(m, gd, rng)
    return msgs
