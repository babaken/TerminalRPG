"""シナリオスクリプトとデータの突き合わせ検証（基本設計 15 章 L001〜L009 のスクリプト部分）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..data.models import GameData
from ..data.report import Report
from ..ui import markup
from .expr import ExprError, names, parse_expr
from .parser import RESERVED_LABELS, Script

if TYPE_CHECKING:
    from ..package import Package

MAP = "Map.data"
SLIDE_SIDES = ("left", "right", "top", "bottom")
TINTS = ("none", "night", "sepia", "red", "invert")


def lint_script(script: Script, gd: GameData, rep: Report, pkg: Optional["Package"] = None,
                start_label: str = "start") -> None:
    labels = script.labels
    referenced: set[str] = set()
    flags_set: set[str] = set()
    flags_used: list[tuple[str, str, int]] = []
    npc_ids = {n.id for m in gd.maps.values() for n in m.npcs}
    targets: list = []

    def label_ref(label: str, file: str, line: Optional[int]) -> None:
        referenced.add(label)
        if label not in labels:
            rep.error(file, line, f"ラベル *{label} が scenario.sco にありません")

    def collect_flags(ast, file: str, line: int) -> None:
        for path in names(ast):
            if path[0] == "flag" and len(path) == 2:
                flags_used.append((path[1], file, line))

    # データ側から参照されるラベル（NPC の会話、イベント、アイテム使用、クエスト達成）
    for label, file, line in gd.label_refs:
        label_ref(label, file, line)

    # データ側の when 条件式
    for m in gd.maps.values():
        line = getattr(m, "_line", None)
        for kind, objs in (("NPC", m.npcs), ("イベント", m.events)):
            for o in objs:
                if not o.when:
                    continue
                try:
                    collect_flags(parse_expr(o.when), MAP, line or 0)
                except ExprError as e:
                    rep.error(MAP, line, f"マップ {m.id} の{kind}の when 条件式の誤り: {e}")

    if start_label not in labels:
        rep.error("scenario.sco", None, f"開始ラベル *{start_label} がありません")
    referenced.add(start_label)

    def need(store: dict, ident: str, kind: str, ins) -> None:
        if ident not in store:
            rep.error(ins.file, ins.line, f"{kind}「{ident}」が定義されていません")

    for ins in script.instrs:
        a = ins.args
        if ins.op in ("goto", "call"):
            label_ref(a["label"], ins.file, ins.line)
        elif ins.op == "choice":
            for text, label, line in a["options"]:
                if label:
                    label_ref(label, ins.file, line)
                for err in markup.check(text):
                    rep.error(ins.file, line, err)
        elif ins.op == "msg":
            for i, (_, text) in enumerate(a["lines"]):
                for err in markup.check(text):
                    rep.error(ins.file, ins.line + i, err)
        elif ins.op == "jif":
            collect_flags(a["cond"], ins.file, ins.line)
        elif ins.op == "cmd":
            name, pos, kw = a["name"], a["pos"], a["kw"]
            if name == "var":
                collect_flags(a["expr"], ins.file, ins.line)
            elif name == "flag" and pos[0] == "set":
                flags_set.add(pos[1])
            elif name == "map":
                mp = gd.maps.get(pos[0])
                if mp is None:
                    need(gd.maps, pos[0], "マップ", ins)
                else:
                    x, y = int(pos[1]), int(pos[2])
                    if not mp.in_bounds(x, y):
                        rep.error(ins.file, ins.line, f"@map {mp.id}: 座標 ({x}, {y}) がマップ外です（{mp.width}×{mp.height}）")
                    else:
                        ts = gd.tilesets.get(mp.tileset)
                        tile = ts.tiles.get(mp.rows[y][x]) if ts else None
                        if tile is not None and not tile.passable:
                            rep.warning(ins.file, ins.line, f"@map {mp.id}: 座標 ({x}, {y}) は通行できないタイル（{tile.name or tile.char}）です")
            elif name == "pet":
                if pos[0] != "release":
                    need(gd.enemies, pos[0], "敵", ins)
            elif name == "tile":
                ch = pos[2]
                mp = gd.maps.get(kw["map"]) if kw.get("map") else None
                if kw.get("map") and mp is None:
                    need(gd.maps, kw["map"], "マップ", ins)
                elif mp is not None:
                    x, y = int(pos[0]), int(pos[1])
                    ts = gd.tilesets.get(mp.tileset)
                    if not mp.in_bounds(x, y):
                        rep.error(ins.file, ins.line, f"@tile: 座標 ({x}, {y}) がマップ {mp.id} の外です（{mp.width}×{mp.height}）")
                    if ts is not None and ch not in ts.tiles:
                        rep.error(ins.file, ins.line, f"@tile: 「{ch}」はマップ {mp.id} のタイルセット {ts.id} にありません")
                elif not any(ch in ts.tiles for ts in gd.tilesets.values()):
                    rep.error(ins.file, ins.line, f"@tile: 「{ch}」はどのタイルセットにもありません")
            elif name == "item":
                need(gd.items, pos[1], "アイテム", ins)
            elif name == "party":
                need(gd.characters, pos[1], "キャラクター", ins)
            elif name == "equip":
                need(gd.characters, pos[0], "キャラクター", ins)
                it = gd.items.get(pos[1])
                if it is None:
                    need(gd.items, pos[1], "アイテム", ins)
                elif it.type != "equipment":
                    rep.error(ins.file, ins.line, f"@equip: 「{pos[1]}」は装備品ではありません")
            elif name == "recruit":
                for cid in pos:
                    need(gd.characters, cid, "キャラクター", ins)
            elif name == "quest":
                need(gd.quests, pos[1], "クエスト", ins)
            elif name == "shop":
                need(gd.shops, pos[0], "ショップ", ins)
            elif name == "battle":
                need(gd.groups, kw["group"], "敵グループ", ins)
                if "lose" in kw:
                    label_ref(kw["lose"].lstrip("*"), ins.file, ins.line)
                if "target_only" in kw:
                    need(gd.characters, kw["target_only"], "キャラクター", ins)
            elif name == "npc":
                if pos[0] not in npc_ids:
                    rep.error(ins.file, ins.line, f"NPC「{pos[0]}」はどのマップにもいません")
            elif name == "face" and pos[0] != "none" and pkg is not None:
                if gd.face_path(pos[0], pkg.exists) is None:
                    rep.error(ins.file, ins.line, f"@face：「{pos[0]}」の顔 AA がありません"
                              f"（Friends.data の face か aa/face_{pos[0]}.txt を用意してください）")
            elif name == "aa" and pos[0] == "show" and pkg is not None:
                if not pkg.exists(pos[1]):
                    rep.error(ins.file, ins.line, f"AA ファイル「{pos[1]}」が見つかりません")
            elif name == "effect" and pos:
                eff, rest = pos[0], pos[1:]
                if eff == "aa_show":
                    if len(rest) < 3 or not all(p.lstrip("-").isdigit() for p in rest[1:3]):
                        rep.error(ins.file, ins.line, "@effect aa_show は「ファイル x y」の形で書いてください")
                    elif pkg is not None and not pkg.exists(rest[0]):
                        rep.error(ins.file, ins.line, f"AA ファイル「{rest[0]}」が見つかりません")
                    if kw.get("from", "left") not in SLIDE_SIDES:
                        rep.error(ins.file, ins.line, f"@effect aa_show の from は {' / '.join(SLIDE_SIDES)} です")
                elif eff == "aa_hide" and kw.get("to", "left") not in SLIDE_SIDES:
                    rep.error(ins.file, ins.line, f"@effect aa_hide の to は {' / '.join(SLIDE_SIDES)} です")
                elif eff == "scroll_text":
                    if "file" in kw:
                        if pkg is not None and not pkg.exists(kw["file"]):
                            rep.error(ins.file, ins.line, f"ファイル「{kw['file']}」が見つかりません")
                    elif not rest:
                        rep.error(ins.file, ins.line, "@effect scroll_text には file= か表示する文字を指定してください")
                elif eff in ("move", "blink"):
                    target = kw.get("target", rest[0] if rest else "")
                    if not target:
                        rep.error(ins.file, ins.line, f"@effect {eff} には対象（NPC ID・hero・AA の名前）を指定してください")
                    else:
                        targets.append((target, eff, ins))
                    nums = [p for p in (rest[1:] if "target" not in kw else rest) if p.lstrip("-").isdigit()]
                    if eff == "move" and len(nums) < 2:
                        rep.error(ins.file, ins.line, "@effect move は「対象 dx dy」の形で書いてください")
                elif eff == "tint" and rest and rest[0] not in TINTS:
                    rep.error(ins.file, ins.line, f"tint は {' / '.join(TINTS)} のどれかです")
                elif eff == "wipe":
                    d = kw.get("dir", next((p for p in rest if not p.isdigit() and p != "out"), "right"))
                    if d not in ("left", "right", "up", "down"):
                        rep.error(ins.file, ins.line, "wipe の向きは left / right / up / down です")

    # move / blink の対象：hero・どこかのマップの NPC・スクリプトで表示する AA の名前
    aa_names = set()
    for ins in script.instrs:
        if ins.op == "cmd":
            a = ins.args
            if a["name"] == "aa" and a["pos"] and a["pos"][0] == "show" and len(a["pos"]) > 1:
                aa_names.add(a["kw"].get("name", a["pos"][1]))
            if a["name"] == "effect" and a["pos"][:1] == ["aa_show"] and len(a["pos"]) > 1:
                aa_names.add(a["kw"].get("name", a["pos"][1]))
    for target, eff, ins in targets:
        if target != "hero" and target not in npc_ids and target not in aa_names:
            rep.error(ins.file, ins.line, f"@effect {eff}：対象「{target}」はどのマップの NPC でも、表示する AA の名前でもありません")

    for label, (file, line) in script.label_lines.items():
        if label not in referenced and label not in RESERVED_LABELS:
            rep.warning(file, line, f"ラベル *{label} はどこからも使われていません")

    warned = set()
    for flag, file, line in flags_used:
        if flag not in flags_set and flag not in warned:
            warned.add(flag)
            rep.warning(file, line, f"フラグ {flag} は参照されていますが、@flag set されている箇所がありません")
