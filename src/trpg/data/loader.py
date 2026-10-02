"""パッケージ内の .data（TOML）を読み込み、GameData を組み立てて検証する。

    rep = Report()
    data = load_game_data(pkg, rep)
    if not rep.ok:
        print(rep.format())
"""
from __future__ import annotations

import re
import tomllib
import unicodedata
from typing import TYPE_CHECKING, Iterator, Optional

from ..term.width import text_width
from .models import (AI_TYPES, BUILTIN_SKILLS, ELEMENTS, EQUIP_SLOTS, EVENT_TRIGGERS, ITEM_TYPES,
                     NPC_MOVES, QUEST_GOALS, ROUTE_STEPS, SKILL_KINDS, STAT_KEYS, TARGETS, USE_EFFECTS, Character,
                     Encounter, Enemy, EnemyAction, GameData, GameMap, Group, Item, Job, MapEvent, Npc,
                     Quest, Shop, Skill, StatusDef, Tile, TileSet, Warp)
from ..term.style import color as to_color
from .models import SKILL_ANIMS, parse_anim
from .reader import REQUIRED, Tbl
from ..script.expr import ExprError, parse_expr
from .report import DataError, Report, find_id_line, find_table_line, toml_error

if TYPE_CHECKING:
    from ..package import Package

FRIENDS = "Friends.data"
ENEMY = "Enemy.data"
ITEMS = "Items.data"
MAP = "Map.data"
QUESTS = "Quests.data"
MANIFEST = "manifest.toml"

DIRS = ("up", "down", "left", "right")
_TARGET_RE = re.compile(r"^(random|lowest_hp|all|id:[a-z][a-z0-9_]*)$")


class _File:
    """1 ファイル分の読み込み状態。"""

    def __init__(self, pkg: "Package", name: str, rep: Report, required: bool):
        self.name = name
        self.rep = rep
        self.text = pkg.read_text(name) or ""
        self.doc: dict = {}
        if not pkg.exists(name):
            if required:
                rep.error(name, None, "必須ファイルがありません")
            return
        try:
            self.doc = tomllib.loads(self.text)
        except tomllib.TOMLDecodeError as e:
            toml_error(rep, name, e)
        self._used: set[str] = set()

    def entries(self, key: str) -> Iterator[Tbl]:
        self._used = getattr(self, "_used", set())
        self._used.add(key)
        raw = self.doc.get(key, [])
        if not isinstance(raw, list):
            self.rep.error(self.name, None, f"{key} は [[{key}]] の形式（テーブルの配列）で書いてください")
            return
        for i, d in enumerate(raw):
            ident = d.get("id") if isinstance(d, dict) else None
            if isinstance(ident, str):
                line = find_id_line(self.text, ident) or find_table_line(self.text, key, i)
                where = f"[[{key}]] {ident}"
            else:
                line = find_table_line(self.text, key, i)
                where = f"[[{key}]] {i + 1} 番目"
            yield Tbl(d, self.name, where, self.rep, line)

    def done(self) -> None:
        for k in self.doc:
            if k not in getattr(self, "_used", set()):
                self.rep.warning(self.name, None, f"未知の項目 [{k}] です（綴りを確認してください）")


def _register(store: dict, obj, t: Tbl, kind: str) -> None:
    if not obj.id:
        return
    if obj.id in store:
        t.report.error(t.file, t.line, f"{kind} の ID「{obj.id}」が重複しています")
        return
    store[obj.id] = obj


def _stats(t: Tbl, key: str, required: tuple[str, ...] = ()) -> dict:
    s = t.sub(key, {} if not required else REQUIRED)
    out = {k: s.int(k, REQUIRED if k in required else 0, min=0) for k in STAT_KEYS}
    s.done()
    return out


# ====================================================================== Friends.data
def _load_friends(f: _File, gd: GameData) -> None:
    for t in f.entries("job"):
        skills = []
        for st in t.table_list("skills", []):
            skills.append((st.int("lv", min=1), st.str("skill")))
            st.done()
        job = Job(id=t.id(), name=t.str("name"), growth=_stats(t, "growth"),
                  equip=t.strlist("equip", []), skills=skills)
        t.done()
        _register(gd.jobs, job, t, "職業")
    for t in f.entries("character"):
        eq = t.sub("equip", {})
        equip = {}
        for slot in list(eq.data):
            if slot not in EQUIP_SLOTS:
                eq._err(slot, f"装備欄は {', '.join(EQUIP_SLOTS)} のどれかです")
                eq.used.add(slot)
                continue
            v = eq.str(slot)
            if v:
                equip[slot] = v
        c = Character(id=t.id(), name=t.str("name"), job=t.str("job"), lv=t.int("lv", 1, min=1, max=99),
                      stats=_stats(t, "stats", ("hp",)), equip=equip, face=t.str("face", ""),
                      name_input=t.bool("name_input", False), recruit_text=t.str("recruit_text", ""))
        t.done()
        _register(gd.characters, c, t, "キャラクター")
        c._line = t.line  # type: ignore[attr-defined]
    f.done()


# ====================================================================== Enemy.data
def _load_enemies(f: _File, gd: GameData) -> None:
    for t in f.entries("enemy"):
        drops = []
        for d in t.table_list("drops", []):
            drops.append((d.str("item"), d.num("rate", min=0.0, max=1.0)))
            d.done()
        actions = []
        for a in t.table_list("actions", []):
            actions.append(EnemyAction(skill=a.str("skill"), weight=a.int("weight", 1, min=0),
                                       when=a.str("when", ""), target=a.str("target", "random")))
            if not _TARGET_RE.match(actions[-1].target):
                a._err("target", f"「{actions[-1].target}」は使えません（random / lowest_hp / all / id:キャラID）")
            a.done()
        e = Enemy(id=t.id(), name=t.str("name"), aa=t.str("aa"), stats=_stats(t, "stats", ("hp",)),
                  exp=t.int("exp", 0, min=0), gold=t.int("gold", 0, min=0),
                  weak=t.strlist("weak", []), resist=t.strlist("resist", []),
                  immune_status=t.strlist("immune_status", []), drops=drops,
                  tameable=t.bool("tameable", False), tame_rate=t.num("tame_rate", 0.0, min=0.0, max=1.0),
                  ai=t.str("ai", "attack_only", choices=AI_TYPES), actions=actions, copy=t.str("copy", ""))
        for k in ("weak", "resist"):
            for el in getattr(e, k):
                if el not in ELEMENTS:
                    t._err(k, f"属性「{el}」は使えません（{', '.join(ELEMENTS)}）")
        if e.ai != "attack_only" and not e.actions:
            t._err("actions", f"ai = \"{e.ai}\" のときは [[enemy.actions]] を 1 つ以上書いてください")
        t.done()
        _register(gd.enemies, e, t, "敵")
        e._line = t.line  # type: ignore[attr-defined]
    for t in f.entries("group"):
        g = Group(id=t.id(), members=t.strlist("members"))
        if not g.members:
            t._err("members", "敵を 1 体以上指定してください")
        elif len(g.members) > 5:
            t._warn("members", f"{len(g.members)} 体は多すぎて画面に並ばない可能性があります（目安 5 体まで）")
        t.done()
        _register(gd.groups, g, t, "敵グループ")
        g._line = t.line  # type: ignore[attr-defined]
    for t in f.entries("encounter"):
        table = []
        for r in t.table_list("table"):
            table.append((r.str("group"), r.int("weight", 1, min=1)))
            r.done()
        en = Encounter(id=t.id(), steps=t.intpair("steps", (16, 32)), table=table)
        if en.steps[0] < 1:
            t._err("steps", "1 歩以上にしてください")
        t.done()
        _register(gd.encounters, en, t, "出現表")
        en._line = t.line  # type: ignore[attr-defined]
    f.done()


# ====================================================================== Items.data
def _load_items(f: _File, gd: GameData) -> None:
    for t in f.entries("item"):
        typ = t.str("type", choices=ITEM_TYPES)
        use_t = t.sub("use", {})
        use = {}
        if use_t.data:
            use = {
                "field": use_t.bool("field", False),
                "battle": use_t.bool("battle", False),
                "target": use_t.str("target", "self", choices=TARGETS),
                "effect": use_t.str("effect", choices=USE_EFFECTS),
                "power": use_t.int("power", 0, min=0),
                "label": use_t.str("label", ""),
                "skill": use_t.str("skill", ""),
                "status": use_t.str("status", ""),
                "consume": use_t.bool("consume", typ == "consumable"),
                "when": use_t.str("when", ""),           # 使える条件（例 "map.dungeon"）
                "to": use_t.str("to", ""),               # effect = "warp" の行き先
                "x": use_t.int("x", 0, min=0),
                "y": use_t.int("y", 0, min=0),
                "dir": use_t.str("dir", "", choices=DIRS + ("",)),
            }
            if use["effect"] == "warp" and not use["to"]:
                use_t._err("to", "effect = \"warp\" のときは行き先のマップ（to）を指定してください")
            if use["when"]:
                try:
                    parse_expr(use["when"])
                except ExprError as e:
                    use_t._err("when", f"条件式の誤り: {e}")
            if use["effect"] == "script" and not use["label"]:
                use_t._err("label", "effect = \"script\" のときは呼び出すラベルを指定してください")
            if use["effect"] == "skill" and not use["skill"]:
                use_t._err("skill", "effect = \"skill\" のときはスキル ID を指定してください")
            use_t.done()
        it = Item(id=t.id(), name=t.str("name"), type=typ, price=t.int("price", 0, min=0),
                  desc=t.str("desc", ""), slot=t.str("slot", ""), category=t.str("category", ""),
                  stats=_stats(t, "stats") if t.has("stats") else {}, use=use)
        if typ == "equipment":
            if it.slot not in EQUIP_SLOTS:
                t._err("slot", f"装備品は slot を指定してください（{', '.join(EQUIP_SLOTS)}）")
        elif it.slot:
            t._warn("slot", "装備品以外では slot は使われません")
        t.done()
        _register(gd.items, it, t, "アイテム")
        it._line = t.line  # type: ignore[attr-defined]
    for t in f.entries("skill"):
        sk = Skill(id=t.id(), name=t.str("name"), mp=t.int("mp", 0, min=0),
                   target=t.str("target", "enemy_one", choices=TARGETS),
                   kind=t.str("kind", "physical", choices=SKILL_KINDS),
                   element=t.str("element", "", choices=ELEMENTS + ("",)),
                   power=t.int("power", 0, min=0), status=t.str("status", ""),
                   status_rate=t.num("status_rate", 1.0 if t.has("status") else 0.0, min=0.0, max=1.0),
                   anim=t.str("anim", ""), desc=t.str("desc", ""))
        for aname, aarg in parse_anim(sk.anim):
            if aname not in SKILL_ANIMS:
                t._err("anim", f"演出「{aname}」はありません（{', '.join(SKILL_ANIMS)}）")
            elif aname == "flash" and aarg:
                try:
                    to_color(aarg)
                except ValueError:
                    t._err("anim", f"flash の色「{aarg}」が不正です")
            elif aname == "shake" and aarg and not aarg.isdigit():
                t._err("anim", f"shake の強さ「{aarg}」は 1〜3 の数字です")
        if sk.id in BUILTIN_SKILLS:
            t._err("id", f"「{sk.id}」はエンジン組み込みのスキル名なので使えません")
        t.done()
        _register(gd.skills, sk, t, "スキル")
        sk._line = t.line  # type: ignore[attr-defined]
    for t in f.entries("status"):
        tick = t.sub("tick", {})
        tick_d = {"hp_rate": tick.num("hp_rate", 0.0, min=-1.0, max=1.0)}
        tick.done()
        st = StatusDef(id=t.id(), name=t.str("name"), turns=t.intpair("turns", (3, 3)), tick=tick_d,
                       on_field=t.bool("field", False), skip_turn=t.bool("skip_turn", False))
        t.done()
        _register(gd.statuses, st, t, "状態異常")
    for t in f.entries("shop"):
        sh = Shop(id=t.id(), name=t.str("name"), goods=t.strlist("goods"),
                  sell_rate=t.num("sell_rate", 0.5, min=0.0, max=1.0))
        t.done()
        _register(gd.shops, sh, t, "ショップ")
        sh._line = t.line  # type: ignore[attr-defined]
    f.done()


# ====================================================================== Map.data
def _is_ambiguous(text: str) -> bool:
    return any(unicodedata.east_asian_width(c) == "A" for c in text)


def _load_maps(f: _File, gd: GameData) -> None:
    for t in f.entries("tileset"):
        tiles: dict[str, Tile] = {}
        tt = t.sub("tiles")
        for ch in list(tt.data):
            tt.used.add(ch)
            if len(ch) != 1:
                tt._err(ch, "タイルの記号は 1 文字にしてください")
                continue
            d = Tbl(tt.data[ch], f.name, f"{t.where} のタイル「{ch}」", f.rep, t.line)
            tile = Tile(char=ch, glyph=d.str("glyph"), passable=d.bool("pass"),
                        color=d.str("color", ""), name=d.str("name", ""))
            w = text_width(tile.glyph)
            if w != 2:
                d._err("glyph", f"「{tile.glyph}」の表示幅が {w} です。全角 1 文字か半角 2 文字（幅 2）にしてください")
            elif _is_ambiguous(tile.glyph):
                d._warn("glyph", f"「{tile.glyph}」は曖昧幅の文字を含み、端末によって表示がずれます。全角文字（例: ＃ 木）を推奨します")
            d.done()
            tiles[ch] = tile
        ts = TileSet(id=t.id(), tiles=tiles)
        t.done()
        _register(gd.tilesets, ts, t, "タイルセット")

    for t in f.entries("map"):
        rows = t.strlist("rows")
        if not rows:
            t._err("rows", "マップの行を 1 行以上書いてください")
        else:
            w0 = len(rows[0])
            for i, r in enumerate(rows):
                if len(r) != w0:
                    t._err("rows", f"{i + 1} 行目の長さ（{len(r)}）が 1 行目（{w0}）と違います")
        events = []
        for e in t.table_list("event", []):
            events.append(MapEvent(x=e.int("x", min=0), y=e.int("y", min=0), label=e.str("label"),
                                   trigger=e.str("trigger", "check", choices=EVENT_TRIGGERS),
                                   once=e.bool("once", False), when=e.str("when", "")))
            e.done()
        warps = []
        for w in t.table_list("warp", []):
            warps.append(Warp(x=w.int("x", min=0), y=w.int("y", min=0), to=w.str("to"),
                              tx=w.int("tx", min=0), ty=w.int("ty", min=0),
                              dir=w.str("dir", "", choices=DIRS + ("",))))
            w.done()
        npcs = []
        for n in t.table_list("npc", []):
            npcs.append(Npc(id=n.id(), glyph=n.str("glyph"), x=n.int("x", min=0), y=n.int("y", min=0),
                            color=n.str("color", ""), move=n.str("move", "fixed", choices=NPC_MOVES),
                            talk=n.str("talk", ""), when=n.str("when", ""), route=n.strlist("route", [])))
            npc = npcs[-1]
            bad = [r for r in npc.route if r not in ROUTE_STEPS]
            if bad:
                n._err("route", f"道順に使えるのは {' / '.join(ROUTE_STEPS)} です（「{bad[0]}」）")
            if npc.move == "route" and not npc.route:
                n._err("route", "move = \"route\" のときは route に道順を書いてください")
            elif npc.route and npc.move != "route":
                n._warn("route", "move が \"route\" でないので route は使われません")
            gw = text_width(npcs[-1].glyph)
            if gw != 2:
                n._err("glyph", f"「{npcs[-1].glyph}」の表示幅が {gw} です。幅 2 にしてください")
            n.done()
        m = GameMap(id=t.id(), name=t.str("name"), tileset=t.str("tileset", "default"), rows=rows,
                    encounter=t.str("encounter", ""), dark=t.bool("dark", False),
                    indoor=t.bool("indoor", False), dungeon=t.bool("dungeon", False),
                    events=events, warps=warps, npcs=npcs)
        t.raw("bgm")  # 予約項目（音なしのため未使用）
        t.done()
        _register(gd.maps, m, t, "マップ")
        m._line = t.line  # type: ignore[attr-defined]
    f.done()


# ====================================================================== Quests.data
def _load_quests(f: _File, gd: GameData) -> None:
    for t in f.entries("quest"):
        g = t.sub("goal")
        goal = {"type": g.str("type", choices=QUEST_GOALS)}
        for k in ("item", "group", "map", "flag"):
            if g.has(k):
                goal[k] = g.str(k)
        goal["count"] = g.int("count", 1, min=1)
        need = {"deliver": "item", "defeat": "group", "reach": "map", "flag": "flag"}.get(goal["type"])
        if need and need not in goal:
            g._err(need, f"type = \"{goal['type']}\" のときは {need} を指定してください")
        g.done()
        r = t.sub("reward", {})
        reward = {"gold": r.int("gold", 0, min=0), "exp": r.int("exp", 0, min=0), "items": r.strlist("items", [])}
        r.done()
        q = Quest(id=t.id(), name=t.str("name"), goal=goal, reward=reward, giver=t.str("giver", "guild"),
                  desc=t.str("desc", ""), rank=t.str("rank", ""), repeatable=t.bool("repeatable", False),
                  on_complete=t.str("on_complete", ""), when=t.str("when", ""))
        t.done()
        _register(gd.quests, q, t, "クエスト")
        q._line = t.line  # type: ignore[attr-defined]
    f.done()


# ====================================================================== AA
def _load_aa(pkg: "Package", gd: GameData, rep: Report, refs: list[tuple[str, str, Optional[int]]]) -> None:
    paths = {p for p in pkg.files() if p.startswith("aa/") and p.endswith(".txt")}
    for path, file, line in refs:
        if path and not pkg.exists(path):
            rep.error(file, line, f"AA ファイル「{path}」が見つかりません")
    for path in sorted(paths):
        text = pkg.read_text(path) or ""
        lines = text.rstrip("\n").split("\n")
        if lines and lines[0].startswith(";;"):
            lines = lines[1:]  # メタ行（配置基準など）は後工程で解釈
        gd.aa[path] = [ln.rstrip("\r") for ln in lines]
    # 色ファイル（aa/xxx.color）。AA と同じ行・文字位置に色コード
    from ..ui.aa import VALID_CODES
    for cpath in sorted(p for p in pkg.files() if p.startswith("aa/") and p.endswith(".color")):
        apath = cpath[:-6] + ".txt"
        crow = [ln.rstrip("\r") for ln in (pkg.read_text(cpath) or "").rstrip("\n").split("\n")]
        if apath not in gd.aa:
            rep.warning(cpath, None, f"対応する AA ファイル「{apath}」がありません")
            continue
        art = gd.aa[apath]
        if len(crow) > len(art):
            rep.warning(cpath, len(art) + 1, f"AA（{len(art)} 行）より行が多くなっています")
        for i, row in enumerate(crow):
            bad = sorted({c for c in row if c not in VALID_CODES})
            if bad:
                rep.error(cpath, i + 1, f"色コード {' '.join(repr(b) for b in bad)} は使えません"
                          "（k r g y b m c w と大文字、. か空白）")
            if i < len(art) and len(row) > len(art[i]):
                rep.warning(cpath, i + 1, f"AA の行（{len(art[i])} 文字）より長くなっています")
        gd.aa_color[apath] = crow


# ====================================================================== 相互参照
def _cross_check(gd: GameData, manifest, rep: Report) -> None:
    def ln(obj) -> Optional[int]:
        return getattr(obj, "_line", None)

    def need(store: dict, ident: str, kind: str, file: str, line, where: str) -> None:
        if ident and ident not in store:
            rep.error(file, line, f"{where}: {kind}「{ident}」が定義されていません")

    skills_all = set(gd.skills) | set(BUILTIN_SKILLS)

    for j in gd.jobs.values():
        for lv, s in j.skills:
            if s not in skills_all:
                rep.error(FRIENDS, None, f"職業 {j.id} の習得スキル「{s}」が定義されていません")
    for c in gd.characters.values():
        need(gd.jobs, c.job, "職業", FRIENDS, ln(c), f"キャラクター {c.id}")
        for slot, iid in c.equip.items():
            it = gd.items.get(iid)
            if it is None:
                rep.error(FRIENDS, ln(c), f"キャラクター {c.id} の装備「{iid}」が定義されていません")
            elif it.type != "equipment" or it.slot != slot:
                rep.error(FRIENDS, ln(c), f"キャラクター {c.id} の {slot} に「{iid}」は装備できません（slot = {it.slot or 'なし'}）")
    for e in gd.enemies.values():
        for iid, _ in e.drops:
            need(gd.items, iid, "アイテム", ENEMY, ln(e), f"敵 {e.id} のドロップ")
        for a in e.actions:
            if a.skill not in skills_all:
                rep.error(ENEMY, ln(e), f"敵 {e.id} の行動スキル「{a.skill}」が定義されていません")
            if a.target.startswith("id:"):
                need(gd.characters, a.target[3:], "キャラクター", ENEMY, ln(e), f"敵 {e.id} の target")
        for s in e.immune_status:
            need(gd.statuses, s, "状態異常", ENEMY, ln(e), f"敵 {e.id} の immune_status")
    for g in gd.groups.values():
        for m in g.members:
            need(gd.enemies, m, "敵", ENEMY, ln(g), f"敵グループ {g.id}")
    for en in gd.encounters.values():
        for gid, _ in en.table:
            need(gd.groups, gid, "敵グループ", ENEMY, ln(en), f"出現表 {en.id}")
    for it in gd.items.values():
        if it.use.get("skill"):
            need(gd.skills, it.use["skill"], "スキル", ITEMS, ln(it), f"アイテム {it.id}")
        if it.use.get("status"):
            need(gd.statuses, it.use["status"], "状態異常", ITEMS, ln(it), f"アイテム {it.id}")
        if it.use.get("label"):
            gd.label_refs.append((it.use["label"], ITEMS, ln(it)))
        if it.use.get("effect") == "warp" and it.use.get("to"):
            to = it.use["to"]
            need(gd.maps, to, "マップ", ITEMS, ln(it), f"アイテム {it.id} の行き先")
            mp = gd.maps.get(to)
            if mp is not None and not mp.in_bounds(it.use["x"], it.use["y"]):
                rep.error(ITEMS, ln(it), f"アイテム {it.id} の行き先 ({it.use['x']}, {it.use['y']}) がマップ {to} の外です")
    for sk in gd.skills.values():
        if sk.status:
            need(gd.statuses, sk.status, "状態異常", ITEMS, ln(sk), f"スキル {sk.id}")
    for sh in gd.shops.values():
        for iid in sh.goods:
            need(gd.items, iid, "アイテム", ITEMS, ln(sh), f"ショップ {sh.id}")

    for m in gd.maps.values():
        ts = gd.tilesets.get(m.tileset)
        if ts is None:
            rep.error(MAP, ln(m), f"マップ {m.id}: タイルセット「{m.tileset}」が定義されていません")
        else:
            bad = sorted({ch for r in m.rows for ch in r if ch not in ts.tiles})
            if bad:
                rep.error(MAP, ln(m), f"マップ {m.id}: タイルセット {ts.id} にない記号があります: {' '.join(repr(b) for b in bad)}")
        need(gd.encounters, m.encounter, "出現表", MAP, ln(m), f"マップ {m.id}")

        def passable(mp: GameMap, x: int, y: int) -> bool:
            t = gd.tilesets.get(mp.tileset)
            if t is None or not mp.in_bounds(x, y):
                return True
            tile = t.tiles.get(mp.rows[y][x])
            return tile is None or tile.passable

        for e in m.events:
            if not m.in_bounds(e.x, e.y):
                rep.error(MAP, ln(m), f"マップ {m.id}: イベント（{e.label}）の座標 ({e.x}, {e.y}) がマップ外です")
            gd.label_refs.append((e.label, MAP, ln(m)))
        for w in m.warps:
            if not m.in_bounds(w.x, w.y):
                rep.error(MAP, ln(m), f"マップ {m.id}: ワープの座標 ({w.x}, {w.y}) がマップ外です")
            dest = gd.maps.get(w.to)
            if dest is None:
                rep.error(MAP, ln(m), f"マップ {m.id}: ワープ先マップ「{w.to}」が定義されていません")
            elif not dest.in_bounds(w.tx, w.ty):
                rep.error(MAP, ln(m), f"マップ {m.id}: ワープ先 {w.to} ({w.tx}, {w.ty}) がマップ外です")
            elif not passable(dest, w.tx, w.ty):
                rep.warning(MAP, ln(m), f"マップ {m.id}: ワープ先 {w.to} ({w.tx}, {w.ty}) が通行できないタイルです")
        seen = set()
        for n in m.npcs:
            if n.id in seen:
                rep.error(MAP, ln(m), f"マップ {m.id}: NPC の ID「{n.id}」が重複しています")
            seen.add(n.id)
            if not m.in_bounds(n.x, n.y):
                rep.error(MAP, ln(m), f"マップ {m.id}: NPC {n.id} の座標 ({n.x}, {n.y}) がマップ外です")
            elif not passable(m, n.x, n.y):
                rep.warning(MAP, ln(m), f"マップ {m.id}: NPC {n.id} が通行できないタイルの上にいます")
            if n.talk:
                gd.label_refs.append((n.talk, MAP, ln(m)))
            if n.move == "route" and n.route and m.in_bounds(n.x, n.y):
                # 道順をたどって壁にぶつからないか・元の位置に戻るかを確かめる
                x, y = n.x, n.y
                vec = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
                for i, step in enumerate(n.route):
                    if step not in vec:
                        continue
                    x, y = x + vec[step][0], y + vec[step][1]
                    if not m.in_bounds(x, y) or not passable(m, x, y):
                        rep.error(MAP, ln(m), f"マップ {m.id}: NPC {n.id} の道順 {i + 1} 歩目 ({x}, {y}) が通れないマスです")
                        break
                else:
                    if (x, y) != (n.x, n.y):
                        rep.warning(MAP, ln(m), f"マップ {m.id}: NPC {n.id} の道順が元の位置に戻りません"
                                                f"（1 周で ({x - n.x:+d}, {y - n.y:+d}) ずれていきます）")

    for q in gd.quests.values():
        g = q.goal
        if g.get("type") == "deliver":
            need(gd.items, g.get("item", ""), "アイテム", QUESTS, ln(q), f"クエスト {q.id} の goal")
        elif g.get("type") == "defeat":
            gid = g.get("group", "")
            if gid and gid not in gd.groups and gid not in gd.enemies:
                rep.error(QUESTS, ln(q), f"クエスト {q.id} の goal: 敵グループ／敵「{gid}」が定義されていません")
        elif g.get("type") == "reach":
            need(gd.maps, g.get("map", ""), "マップ", QUESTS, ln(q), f"クエスト {q.id} の goal")
        for iid in q.reward.get("items", []):
            need(gd.items, iid, "アイテム", QUESTS, ln(q), f"クエスト {q.id} の報酬")
        if q.on_complete:
            gd.label_refs.append((q.on_complete, QUESTS, ln(q)))

    if manifest is not None:
        for cid in manifest.start_party:
            need(gd.characters, cid, "キャラクター", MANIFEST, None, "[start] party")
        for iid in manifest.start_items:
            need(gd.items, iid, "アイテム", MANIFEST, None, "[start] items")


# ====================================================================== 入口
def load_game_data(pkg: "Package", report: Optional[Report] = None, *, strict: bool = False) -> GameData:
    """パッケージから全データを読む。``strict`` ならエラーがあるとき DataError を送出する。"""
    rep = report if report is not None else Report()
    gd = GameData()
    _load_friends(_File(pkg, FRIENDS, rep, True), gd)
    _load_enemies(_File(pkg, ENEMY, rep, True), gd)
    _load_items(_File(pkg, ITEMS, rep, False), gd)
    _load_maps(_File(pkg, MAP, rep, True), gd)
    _load_quests(_File(pkg, QUESTS, rep, False), gd)

    aa_refs: list[tuple[str, str, Optional[int]]] = []
    aa_refs += [(e.aa, ENEMY, getattr(e, "_line", None)) for e in gd.enemies.values()]
    aa_refs += [(c.face, FRIENDS, getattr(c, "_line", None)) for c in gd.characters.values() if c.face]
    if pkg.manifest.title_aa:
        aa_refs.append((pkg.manifest.title_aa, MANIFEST, None))
    _load_aa(pkg, gd, rep, aa_refs)

    _cross_check(gd, pkg.manifest, rep)
    if strict and not rep.ok:
        raise DataError(rep)
    return gd
