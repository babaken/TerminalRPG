"""戦闘の進行と計算（基本設計 4.5 / 14 章）。画面には依存しない。

使い方::

    b = Battle(gd, state, "slime_2", escape=True)
    for ev in b.intro(): ...                 # 「スライムAがあらわれた！」など
    cmds = {member_battler: Command("attack", target=enemy), ...}
    for ev in b.run_round(cmds): ...         # ラウンドを実行（イベントを順に返す）
    if b.result == "win":
        for ev in b.finish(): ...            # 経験値・お金・ドロップ・レベルアップ

イベントは ``("msg", 文字列)`` ``("hit", Battler)`` ``("heal", Battler)`` ``("clear", None)``。
画面側はこれを順に見せていく。
"""
from __future__ import annotations

from ..i18n import tr

import random
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from ..data.models import BUILTIN_SKILLS, Enemy, GameData, Skill
from ..script.expr import ExprError, evaluate, parse_expr
from ..world import quests as Q
from ..world.growth import gain_exp, skills_of
from ..world.state import GameState, Member, format_text

Event = tuple[str, Any]
LETTERS = "ＡＢＣＤＥＦＧＨ"
COMBAT_STATS = ("atk", "def", "mag", "agi", "luk")


# ====================================================================== 参加者
class Battler:
    """戦闘の参加者。味方は Member の HP/MP を直接読み書きする（戦闘後もそのまま残る）。"""

    def __init__(self, gd: GameData, *, member: Optional[Member] = None, enemy: Optional[Enemy] = None,
                 name: str = "", pet: bool = False):
        self.gd = gd
        self.member = member
        self.enemy = enemy
        self.pet = pet                            # テイムした魔物・使い魔（味方側。自動で行動する）
        self.owner: Optional["Battler"] = None    # 使い魔のとき：主人
        self.side = "party" if member is not None or pet else "enemy"
        self.name = name or (member.name if member else enemy.name)
        self.status: dict[str, int] = {}          # 状態異常 ID → 残りターン
        self.mods: dict[str, list[int]] = {}      # 能力の一時増減 stat → [量, 残りターン]
        self.defending = False
        self.gone = False                         # 逃げた・手なずけられた
        if member is not None:
            for sid in member.status:
                sd = gd.statuses.get(sid)
                self.status[sid] = sd.turns[1] if sd else 3
        else:
            self._hp = enemy.stats.get("hp", 1)
            self._mp = enemy.stats.get("mp", 0)

    # ---- HP / MP
    @property
    def hp(self) -> int:
        return self.member.hp if self.member else self._hp

    @hp.setter
    def hp(self, v: int) -> None:
        v = max(0, min(self.max_hp, v))
        if self.member:
            self.member.hp = v
        else:
            self._hp = v

    @property
    def mp(self) -> int:
        return self.member.mp if self.member else self._mp

    @mp.setter
    def mp(self, v: int) -> None:
        v = max(0, min(self.max_mp, v))
        if self.member:
            self.member.mp = v
        else:
            self._mp = v

    @property
    def sp(self) -> int:
        return max(0, self.member.sp) if self.member else 0

    @sp.setter
    def sp(self, v: int) -> None:
        if self.member:
            self.member.sp = max(0, min(self.max_sp, v))

    @property
    def max_sp(self) -> int:
        return self.member.max_sp(self.gd) if self.member else 0

    @property
    def max_hp(self) -> int:
        return self.member.stat("hp", self.gd) if self.member else self.enemy.stats.get("hp", 1)

    @property
    def max_mp(self) -> int:
        return self.member.stat("mp", self.gd) if self.member else self.enemy.stats.get("mp", 0)

    @property
    def alive(self) -> bool:
        return self.hp > 0 and not self.gone

    @property
    def hp_rate(self) -> float:
        return self.hp / self.max_hp if self.max_hp else 0.0

    def stat(self, key: str) -> int:
        base = self.member.stat(key, self.gd) if self.member else self.enemy.stats.get(key, 0)
        mod = self.mods.get(key)
        return max(0, base + (mod[0] if mod else 0))

    def skills(self) -> list[Skill]:
        if self.member is None:
            return []
        return [self.gd.skills[s] for s in skills_of(self.member, self.gd)]

    def can_act(self) -> bool:
        if not self.alive:
            return False
        return not any(self.gd.statuses.get(s) and self.gd.statuses[s].skip_turn for s in self.status)


@dataclass
class Command:
    kind: str                       # attack / skill / item / defend / escape / tame
    target: Any = None              # Battler / "all" / None
    skill: str = ""
    item: str = ""


class _SelfContext:
    """敵の行動条件（when）用：self.hp_rate などを提供し、他は GameState に任せる。"""

    def __init__(self, me: Battler, battle: "Battle"):
        self.me = me
        self.battle = battle

    def lookup(self, path: tuple[str, ...]) -> Any:
        if path[0] == "self":
            key = path[1] if len(path) > 1 else ""
            return {"hp_rate": self.me.hp_rate, "hp": self.me.hp, "mp": self.me.mp,
                    "turn": self.battle.turn}.get(key, 0)
        return self.battle.st.lookup(path)

    def call(self, path: tuple[str, ...], args: tuple) -> Any:
        return self.battle.st.call(path, args)


# ====================================================================== 戦闘
class Battle:
    def __init__(self, gd: GameData, st: GameState, group_id: str, *, escape: bool = True,
                 target_only: str = "", rng: Optional[random.Random] = None,
                 members: Optional[list[str]] = None, turn_limit: int = 0):
        self.gd = gd
        self.st = st
        self.group_id = group_id
        self.can_escape = escape
        self.target_only = target_only
        # 既定はグローバルの random から種を取る（テストで random.seed() すると再現できる）
        self.rng = rng or random.Random(random.random())
        self.turn = 0
        self.result: Optional[str] = None        # win / lose / escape / timeout（turn_limit ターンたった）
        self.turn_limit = turn_limit
        self.defeated: list[str] = []            # 倒した敵 ID（報酬・討伐依頼用）
        # members を指定すると、その仲間だけが戦う（試練など。ほかの仲間とペットは参加しない）
        self.party = [Battler(gd, member=m) for m in st.party if not members or m.id in members]
        # テイムした魔物（パーティ枠の外で 1 体）。毎回 HP 満タンで参加し、経験値はもらわない
        pet = gd.enemies.get(st.pet) if st.pet and (not members or "pet" in members) else None
        self.pet: Optional[Battler] = Battler(gd, enemy=pet, pet=True) if pet else None
        # 使い魔：主人（Friends.data の familiar）が戦闘に出ていれば一緒に戦う。強さは主人の Lv で決まる
        self.familiars: list[Battler] = []
        for b in self.party:
            ch = gd.characters.get(b.member.id)
            fam = gd.enemies.get(ch.familiar) if ch and ch.familiar else None
            if fam is not None:
                fb = Battler(gd, enemy=self._grown(fam, b.member.lv), pet=True)
                fb.owner = b
                self.familiars.append(fb)
        ids = gd.groups[group_id].members
        counts = {e: ids.count(e) for e in ids}
        seen: dict[str, int] = {}
        self.enemies: list[Battler] = []
        for eid in ids:
            e = self._copied(gd.enemies[eid])
            name = format_text(e.name, st, gd)
            if counts[eid] > 1:
                name += LETTERS[seen.get(eid, 0) % len(LETTERS)]
                seen[eid] = seen.get(eid, 0) + 1
            self.enemies.append(Battler(gd, enemy=e, name=name))
        self._cond_cache: dict[str, Any] = {}

    @staticmethod
    def _grown(e: Enemy, lv: int) -> Enemy:
        """使い魔の能力値：基本値 + growth ×（主人の Lv − 1）。"""
        if not e.growth or lv <= 1:
            return e
        from dataclasses import replace
        stats = {k: v + e.growth.get(k, 0) * (lv - 1) for k, v in e.stats.items()}
        for k, g in e.growth.items():
            stats.setdefault(k, g * (lv - 1))
        return replace(e, stats=stats)

    def _copied(self, e: Enemy) -> Enemy:
        """copy = キャラID の敵は、戦闘開始時のそのキャラの能力値（装備込み）になる。"""
        if not e.copy:
            return e
        m = self.st.member(e.copy)
        if m is None:
            return e
        from dataclasses import replace
        stats = {k: m.stat(k, self.gd) for k in ("hp", "mp", "atk", "def", "mag", "agi", "luk")}
        return replace(e, stats=stats)

    # ---- 状態
    @property
    def allies(self) -> list[Battler]:
        """味方全員（パーティ＋使い魔＋ペット）。"""
        return self.party + self.familiars + ([self.pet] if self.pet else [])

    @property
    def helpers(self) -> list[Battler]:
        """自動で戦う味方（使い魔とペット）。"""
        return self.familiars + ([self.pet] if self.pet else [])

    def alive(self, side: str) -> list[Battler]:
        lst = self.allies if side == "party" else self.enemies
        return [b for b in lst if b.alive]

    def actors(self) -> list[Battler]:
        """コマンドを入力する味方（行動できる人）。"""
        return [b for b in self.party if b.can_act()]

    def _check_end(self) -> bool:
        if self.result:
            return True
        if not self.alive("enemy"):
            self.result = "win"
        elif not any(b.alive for b in self.party):       # ペットだけ残っても負け
            self.result = "lose"
        return self.result is not None

    # ---- 計算
    def _rand(self, lo: float, hi: float) -> float:
        return self.rng.uniform(lo, hi)

    def _elem_rate(self, target: Battler, element: str) -> float:
        if not element or target.enemy is None:
            return 1.0
        if element in target.enemy.weak:
            return 1.5
        if element in target.enemy.resist:
            return 0.5
        return 1.0

    def physical_damage(self, a: Battler, t: Battler, power: int = 0) -> tuple[int, bool, bool]:
        """(ダメージ, 会心か, 回避されたか)。"""
        evade = min(0.2, max(0.0, (t.stat("agi") - a.stat("agi")) / 200))
        if self.rng.random() < evade:
            return 0, False, True
        crit_rate = max(a.stat("luk") / 256, 1 / 32)
        crit = power == 0 and self.rng.random() < crit_rate
        if crit:
            dmg = (a.stat("atk") + power) * 1.5
        else:
            dmg = (a.stat("atk") + power - t.stat("def") / 2) * self._rand(0.9, 1.1)
        if t.defending:
            dmg *= 0.5
        return max(1, int(dmg)), crit, False

    def magic_damage(self, a: Battler, t: Battler, sk: Skill) -> int:
        dmg = (sk.power + a.stat("mag") * 0.8 - t.stat("mag") * 0.3) * self._elem_rate(t, sk.element)
        dmg *= self._rand(0.9, 1.1)
        if t.defending:
            dmg *= 0.5
        return max(1, int(dmg))

    def heal_amount(self, a: Battler, power: int) -> int:
        return int(power + a.stat("mag") * 0.5)

    def escape_rate(self) -> float:
        pa = self.alive("party")
        ea = self.alive("enemy")
        if not pa or not ea:
            return 1.0
        p = sum(b.stat("agi") for b in pa) / len(pa)
        e = sum(b.stat("agi") for b in ea) / len(ea)
        return min(0.95, max(0.2, 0.5 + (p - e) / 100))

    def tame_rate(self, t: Battler) -> float:
        if t.enemy is None or not t.enemy.tameable:
            return 0.0
        return min(0.95, t.enemy.tame_rate * (1 + (1 - t.hp_rate)))

    # ---- 進行
    def intro(self) -> Iterator[Event]:
        names: dict[str, int] = {}
        for b in self.enemies:
            names[b.enemy.name] = names.get(b.enemy.name, 0) + 1
        for n, c in names.items():
            yield ("msg", tr('{0}が {1} 匹あらわれた！', n, c) if c > 1 else tr('{0}があらわれた！', n))
        for h in self.helpers:
            yield ("msg", tr('{0}がいっしょに戦う！', h.name))

    def enemy_command(self, e: Battler) -> Command:
        acts = e.enemy.actions if e.enemy.ai != "attack_only" else []
        cands = []
        for a in acts:
            if a.when and not self._cond(a.when, e):
                continue
            sk = self.gd.skills.get(a.skill)
            if sk is not None and sk.mp > e.mp:
                continue
            cands.append(a)
        if not cands:
            return Command("attack", target=self._enemy_target(e, "random"))
        weights = [max(0, a.weight) for a in cands]
        a = self.rng.choices(cands, weights)[0] if sum(weights) > 0 else cands[0]
        if a.skill == "attack":
            return Command("attack", target=self._enemy_target(e, a.target))
        if a.skill == "defend":
            return Command("defend")
        return Command("skill", skill=a.skill, target=self._enemy_target(e, a.target))

    def pet_command(self, p: Battler) -> Command:
        """ペットの行動：魔物だったときの行動表から選び、敵に向ける（回復などは味方へ）。"""
        foes = self.alive("enemy")
        acts = p.enemy.actions if p.enemy.ai != "attack_only" else []
        cands = []
        for a in acts:
            if a.when and not self._cond(a.when, p):
                continue
            sk = self.gd.skills.get(a.skill)
            if sk is not None and sk.mp > p.mp:
                continue
            cands.append(a)
        a = None
        if cands:
            weights = [max(0, x.weight) for x in cands]
            a = self.rng.choices(cands, weights)[0] if sum(weights) > 0 else cands[0]
        if a is None or a.skill == "attack" or not foes:
            return Command("attack", target=self.rng.choice(foes) if foes else None)
        if a.skill == "defend":
            return Command("defend")
        sk = self.gd.skills.get(a.skill)
        if sk is not None and sk.target in ("ally_one", "self"):
            hurt = min(self.alive("party"), key=lambda b: b.hp_rate, default=p)
            return Command("skill", skill=a.skill, target=hurt)
        return Command("skill", skill=a.skill, target=self.rng.choice(foes))

    def _cond(self, src: str, me: Battler) -> bool:
        ast = self._cond_cache.get(src)
        if ast is None:
            ast = self._cond_cache[src] = parse_expr(src)
        try:
            return bool(evaluate(ast, _SelfContext(me, self)))
        except ExprError:
            return False

    def _enemy_target(self, e: Battler, policy: str) -> Any:
        if self.target_only:
            for b in self.party:
                if b.member.id == self.target_only and b.alive:
                    return b
        alive = self.alive("party")
        if not alive:
            return None
        if policy == "all":
            return "all"
        if policy == "lowest_hp":
            return min(alive, key=lambda b: b.hp)
        if policy.startswith("id:"):
            for b in alive:
                if b.member is not None and b.member.id == policy[3:]:
                    return b
        return self.rng.choice(alive)

    def run_round(self, cmds: dict[Battler, Command]) -> Iterator[Event]:
        """1 ラウンド実行する。cmds は味方の入力（逃げるは 1 人でも選べば全員で逃げる）。"""
        self.turn += 1
        for b in self.allies + self.enemies:
            b.defending = False
        # 逃げる：行動順の前に判定（失敗するとこのターン味方は行動できない）
        if any(c.kind == "escape" for c in cmds.values()):
            yield ("clear", None)
            yield ("msg", tr('{0}たちは逃げ出した！', self.party[0].name))
            if not self.can_escape:
                yield ("msg", tr('しかし、逃げられない！'))
                cmds = {}
            elif self.rng.random() < self.escape_rate():
                yield ("msg", tr('うまく逃げ切れた！'))
                self.result = "escape"
                return
            else:
                yield ("msg", tr('しかし、回りこまれてしまった！'))
                cmds = {}
        order: list[tuple[float, Battler, Command]] = []
        for b, c in cmds.items():
            if b.can_act():
                if c.kind == "defend":
                    b.defending = True      # 防御は行動順に関係なくすぐ有効
                order.append((b.stat("agi") * self._rand(0.8, 1.2), b, c))
        for h in self.helpers:
            if h.can_act() and cmds:
                c = self.pet_command(h)
                if c.kind == "defend":
                    h.defending = True
                order.append((h.stat("agi") * self._rand(0.8, 1.2), h, c))
        for e in self.enemies:
            if e.can_act():
                c = self.enemy_command(e)
                if c.kind == "defend":
                    e.defending = True
                order.append((e.stat("agi") * self._rand(0.8, 1.2), e, c))
        order.sort(key=lambda t: -t[0])
        for _, actor, cmd in order:
            if not actor.alive:
                continue
            if not actor.can_act():
                yield ("clear", None)
                sname = next((self.gd.statuses[s].name for s in actor.status
                              if self.gd.statuses.get(s) and self.gd.statuses[s].skip_turn), "")
                yield ("msg", tr('{0}は{1}で動けない！', actor.name, sname))
                continue
            yield ("clear", None)
            yield from self._act(actor, cmd)
            if self._check_end():
                return
        yield from self._end_of_round()
        if not self._check_end() and self.turn_limit and self.turn >= self.turn_limit:
            self.result = "timeout"

    # ---- 行動
    def _retarget(self, actor: Battler, t: Any, hostile: bool) -> Any:
        """対象が倒れていたら同じ側の別の相手に変える。"""
        side = ("enemy" if actor.side == "party" else "party") if hostile else actor.side
        if t == "all" or (isinstance(t, Battler) and t.alive):
            return t
        alive = self.alive(side)
        return self.rng.choice(alive) if alive else None

    def _targets(self, t: Any, actor: Battler, hostile: bool) -> list[Battler]:
        side = ("enemy" if actor.side == "party" else "party") if hostile else actor.side
        if t == "all":
            return self.alive(side)
        t = self._retarget(actor, t, hostile)
        return [t] if t is not None else []

    def _damage(self, t: Battler, dmg: int) -> Iterator[Event]:
        t.hp -= dmg
        yield ("hit", t)
        if t.side == "enemy":
            yield ("msg", tr('{0}に {1} のダメージ！', t.name, dmg))
        else:
            yield ("msg", tr('{0}は {1} のダメージを受けた！', t.name, dmg))
        if t.hp <= 0:
            if t.side == "enemy":
                self.defeated.append(t.enemy.id)
                yield ("msg", tr('{0}をたおした！', t.name))
            else:
                t.status.clear()
                yield ("msg", tr('{0}はたおれてしまった…', t.name))

    def _act(self, a: Battler, c: Command) -> Iterator[Event]:
        if c.kind == "attack":
            yield ("msg", tr('{0}の攻撃！', a.name))
            for t in self._targets(c.target, a, True)[:1]:
                dmg, crit, miss = self.physical_damage(a, t)
                if miss:
                    yield ("msg", tr('ミス！\u3000{0}はひらりと身をかわした。', t.name))
                    continue
                if crit:
                    yield ("msg", tr('会心の一撃！'))
                yield from self._damage(t, dmg)
        elif c.kind == "defend":
            yield ("msg", tr('{0}は身を守っている。', a.name))
        elif c.kind == "skill":
            yield from self._skill(a, c)
        elif c.kind == "item":
            yield from self._item(a, c)
        elif c.kind == "tame":
            yield from self._tame(a, c)

    def _skill(self, a: Battler, c: Command) -> Iterator[Event]:
        sk = self.gd.skills.get(c.skill)
        if sk is None:
            return
        if a.mp < sk.mp or (a.member is not None and a.sp < sk.sp):
            yield ("msg", tr('{0}は{1}をつかおうとした！', a.name, sk.name))
            yield ("msg", tr('しかし {0} が足りない！', 'MP' if a.mp < sk.mp else 'SP'))
            return
        a.mp -= sk.mp
        if a.member is not None:
            a.sp -= sk.sp
        if sk.kind in ("magic", "heal", "buff", "debuff"):
            yield ("msg", tr('{0}は{1}をとなえた！', a.name, sk.name))
        else:
            yield ("msg", tr('{0}の{1}！', a.name, sk.name))
        if sk.kind == "tame":
            yield from self._tame(a, c)
            return
        if sk.kind == "escape":
            if self.can_escape:
                self.result = "escape"
                yield ("msg", tr('うまく逃げ切れた！'))
            else:
                yield ("msg", tr('しかし、逃げられない！'))
            return
        hostile = sk.target in ("enemy_one", "enemy_all")
        tgt = "all" if sk.target in ("enemy_all", "ally_all") else (a if sk.target == "self" else c.target)
        targets = self._targets(tgt, a, hostile) if sk.target != "self" else [a]
        if not targets:
            yield ("msg", tr('しかし、相手がいなかった。'))
            return
        if sk.anim:
            yield ("anim", (sk.anim, targets))
        for t in targets:
            if sk.kind == "physical":
                dmg, _, miss = self.physical_damage(a, t, sk.power)
                if miss:
                    yield ("msg", tr('ミス！\u3000{0}はひらりと身をかわした。', t.name))
                    continue
                yield from self._damage(t, dmg)
            elif sk.kind == "magic":
                rate = self._elem_rate(t, sk.element)
                yield from self._damage(t, self.magic_damage(a, t, sk))
                if rate > 1:
                    yield ("msg", tr('効果はばつぐんだ！'))
                elif rate < 1:
                    yield ("msg", tr('あまり効いていないようだ…'))
            elif sk.kind == "heal":
                yield from self._heal(t, self.heal_amount(a, sk.power))
            elif sk.kind in ("buff", "debuff"):
                key = "atk" if sk.kind == "buff" else "def"
                amount = max(1, sk.power or 5) * (1 if sk.kind == "buff" else -1)
                t.mods[key] = [amount, 3]
                word = tr('攻撃力が上がった！') if sk.kind == "buff" else tr('守備力が下がった！')
                yield ("msg", tr('{0}の{1}', t.name, word))
            if sk.status and t.alive:
                yield from self._inflict(t, sk.status, sk.status_rate, verbose=sk.kind == "status")

    def _heal(self, t: Battler, amount: int) -> Iterator[Event]:
        if not t.alive:
            yield ("msg", tr('しかし、{0}はたおれている。', t.name))
            return
        before = t.hp
        t.hp += amount
        yield ("heal", t)
        yield ("msg", tr('{0}の HP が {1} 回復した！', t.name, t.hp - before))

    def _inflict(self, t: Battler, sid: str, rate: float, verbose: bool = True) -> Iterator[Event]:
        """状態異常を与える。verbose=False（攻撃のおまけ効果）なら失敗しても何も言わない。"""
        sd = self.gd.statuses.get(sid)
        if sd is None or sid in t.status:
            if verbose and sd is not None:
                yield ("msg", tr('{0}はすでに{1}になっている。', t.name, sd.name))
            return
        if t.enemy is not None and sid in t.enemy.immune_status:
            if verbose:
                yield ("msg", tr('{0}には効かなかった！', t.name))
            return
        if self.rng.random() >= rate:
            if verbose:
                yield ("msg", tr('しかし、{0}には効かなかった。', t.name))
            return
        t.status[sid] = self.rng.randint(*sd.turns)
        yield ("msg", tr('{0}は{1}になった！', t.name, sd.name))

    def _item(self, a: Battler, c: Command) -> Iterator[Event]:
        it = self.gd.items.get(c.item)
        if it is None or self.st.items.get(it.id, 0) <= 0:
            yield ("msg", tr('{0}は道具をつかおうとしたが、もう持っていなかった。', a.name))
            return
        use = it.use
        if use.get("consume", True):
            self.st.remove_item(it.id)
        yield ("msg", tr('{0}は{1}をつかった！', a.name, it.name))
        hostile = use.get("target", "ally_one").startswith("enemy")
        tgt = "all" if use.get("target", "").endswith("_all") else c.target
        for t in self._targets(tgt, a, hostile) if tgt != "self" else [a]:
            eff = use.get("effect")
            if eff == "heal":
                yield from self._heal(t, int(use.get("power", 0)))
            elif eff == "heal_mp":
                before = t.mp
                t.mp += int(use.get("power", 0))
                yield ("msg", tr('{0}の MP が {1} 回復した！', t.name, t.mp - before))
            elif eff == "cure":
                sid = use.get("status", "")
                if sid in t.status:
                    del t.status[sid]
                    yield ("msg", tr('{0}の{1}が治った！', t.name, self.gd.statuses[sid].name))
                else:
                    yield ("msg", tr('しかし、何も起こらなかった。'))
            elif eff == "revive":
                if t.hp <= 0 and not t.gone:
                    t.hp = max(1, t.max_hp * max(1, int(use.get("power", 50))) // 100)
                    yield ("msg", tr('{0}が生き返った！', t.name))
                else:
                    yield ("msg", tr('しかし、何も起こらなかった。'))
            elif eff == "skill" and use.get("skill") in self.gd.skills:
                yield from self._skill(a, Command("skill", target=t, skill=use["skill"]))
                break

    def _tame(self, a: Battler, c: Command) -> Iterator[Event]:
        t = self._retarget(a, c.target, True)
        if not isinstance(t, Battler):
            return
        yield ("msg", tr('{0}は{1}に手をさしのべた…', a.name, t.name))
        if self.rng.random() < self.tame_rate(t):
            t.gone = True
            old = self.gd.enemies.get(self.st.pet) if self.st.pet else None
            self.st.pet = t.enemy.id
            yield ("msg", tr('{0}はなついた！\u3000仲間になった！', t.name))
            if old is not None:
                yield ("msg", tr('いままでの{0}は、野に帰っていった。', old.name))
        else:
            yield ("msg", tr('{0}はそっぽを向いた。', t.name))

    def _end_of_round(self) -> Iterator[Event]:
        cleared = False
        for b in self.party:                         # 味方は毎ターン SP が少し回復する
            job = self.gd.jobs.get(b.member.job)
            if b.alive and job and job.sp_regen:
                b.sp += job.sp_regen
        for b in self.allies + self.enemies:
            if not b.alive:
                continue
            for sid in list(b.status):
                sd = self.gd.statuses.get(sid)
                if sd is None:
                    del b.status[sid]
                    continue
                rate = sd.tick.get("hp_rate", 0.0)
                if rate < 0 and b.alive:
                    if not cleared:
                        yield ("clear", None)
                        cleared = True
                    dmg = max(1, int(b.max_hp * -rate))
                    yield ("msg", tr('{0}は{1}で苦しんでいる！', b.name, sd.name))
                    yield from self._damage(b, dmg)
                    if sid not in b.status:          # 倒れて状態異常が消えた
                        break
                b.status[sid] -= 1
                if b.status[sid] <= 0 and b.alive:
                    del b.status[sid]
                    if not cleared:
                        yield ("clear", None)
                        cleared = True
                    yield ("msg", tr('{0}の{1}が治った。', b.name, sd.name))
            for key in list(b.mods):
                b.mods[key][1] -= 1
                if b.mods[key][1] <= 0:
                    del b.mods[key]

    # ---- 終了
    def finish(self) -> Iterator[Event]:
        """勝利：経験値・お金・ドロップ。逃走・敗北でも状態異常を味方に書き戻す。"""
        for b in self.party:
            b.member.status = [s for s in b.status
                               if b.alive and self.gd.statuses.get(s) and self.gd.statuses[s].on_field]
        if self.result != "win":
            return
        yield ("clear", None)
        yield ("msg", tr('魔物たちをやっつけた！'))
        exp = gold = 0
        for eid in self.defeated:
            e = self.gd.enemies[eid]
            exp += e.exp
            gold += e.gold
        if gold:
            self.st.gold += gold
            yield ("msg", tr('{0} G を手に入れた。', gold))
        for eid in self.defeated:
            for iid, rate in self.gd.enemies[eid].drops:
                if iid in self.gd.items and self.rng.random() < rate:
                    self.st.add_item(iid)
                    yield ("msg", tr('{0}は{1}を落としていった！', self.gd.enemies[eid].name, self.gd.items[iid].name))
        Q.on_defeat(self.st, self.gd, self.defeated, self.group_id)
        for m in gain_exp(self.st, self.gd, exp, self.rng):
            yield ("msg", m)
